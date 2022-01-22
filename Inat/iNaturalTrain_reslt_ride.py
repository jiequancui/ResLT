import argparse
import os
import random
import shutil
import time
import warnings
import math
import numpy as np

import torch
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.distributed as dist
import torch.optim
import torch.multiprocessing as mp
import torch.utils.data
import torch.utils.data.distributed
import torchvision.transforms as transforms
import torchvision.datasets as datasets
import torchvision.models as models
import torch.nn.functional as F

from datasets import dataset
from networks import nets

model_names = sorted(name for name in models.__dict__
    if name.islower() and not name.startswith("__")
    and callable(models.__dict__[name]))

model_names += ['resnext50_32x4d_reslt','resnet10_reslt', 'resnext101_32x4d_reslt', 'ResNeXt50Model', 'ResNet50Model']

parser = argparse.ArgumentParser(description='PyTorch ImageNet Training')
parser.add_argument('--root_path', type=str, default='data')
parser.add_argument('-dataset', type=str,
                    help='path to dataset')
parser.add_argument('--data_path', type=str, default=None)
parser.add_argument('-a', '--arch', metavar='ARCH', default='ResNeXt152',
                    choices=model_names,
                    help='model architecture: ' +
                        ' | '.join(model_names) +
                        ' (default: resnet18)')
parser.add_argument('-j', '--workers', default=32, type=int, metavar='N',
                    help='number of data loading workers (default: 4)')
parser.add_argument('--epochs', default=90, type=int, metavar='N',
                    help='number of total epochs to run')
parser.add_argument('--start-epoch', default=0, type=int, metavar='N',
                    help='manual epoch number (useful on restarts)')
parser.add_argument('-b', '--batch-size', default=None, type=int,
                    metavar='N',
                    help='mini-batch size (default: 256), this is the total '
                         'batch size of all GPUs on the current node when '
                         'using Data Parallel or Distributed Data Parallel')
parser.add_argument('--lr', '--learning-rate', default=0.2, type=float,
                    metavar='LR', help='initial learning rate', dest='lr')
parser.add_argument('--momentum', default=0.9, type=float, metavar='M',
                    help='momentum')
parser.add_argument('--wd', '--weight-decay', default=5e-4, type=float,
                    metavar='W', help='weight decay (default: 1e-4)',
                    dest='weight_decay')
parser.add_argument('-p', '--print-freq', default=100, type=int,
                    metavar='N', help='print frequency (default: 10)')
parser.add_argument('--resume', default='', type=str, metavar='PATH',
                    help='path to latest checkpoint (default: none)')
parser.add_argument('-e', '--evaluate', dest='evaluate', action='store_true',
                    help='evaluate model on validation set')
parser.add_argument('--pretrained', dest='pretrained', action='store_true',
                    help='use pre-trained model')
parser.add_argument('--world-size', default=-1, type=int,
                    help='number of nodes for distributed training')
parser.add_argument('--rank', default=-1, type=int,
                    help='node rank for distributed training')
parser.add_argument('--dist-url', default='tcp://224.66.41.62:23456', type=str,
                    help='url used to set up distributed training')
parser.add_argument('--dist-backend', default='nccl', type=str,
                    help='distributed backend')
parser.add_argument('--seed', default=None, type=int,
                    help='seed for initializing training. ')
parser.add_argument('--gpu', default=None, type=int,
                    help='GPU id to use.')
parser.add_argument('--multiprocessing-distributed', action='store_true',
                    help='Use multi-processing distributed training to launch '
                         'N processes per node, which has N GPUs. This is the '
                         'fastest way to use PyTorch for either single node or '
                         'multi node data parallel training')

# ResLT
parser.add_argument('--mark', default=None, type=str, help='prefix of log file')
parser.add_argument('--beta', default=None, type=float)
parser.add_argument('--num_works', default=None, type=int)
parser.add_argument('--dropout', default=False, type=bool)
parser.add_argument('--lsm', default=0, type=float)
parser.add_argument('--warmup_epochs', default=5, type=int)
parser.add_argument('--after_1x1conv', action='store_true')
parser.add_argument('--gamma', default=0.5, type=float)
parser.add_argument('--num_classes', default=1000, type=int)
parser.add_argument('--val_num_experts', default=3, type=int)


best_acc1 = 0
args = parser.parse_args()
args.root_model = f'{args.root_path}/{args.dataset}/{args.mark}'
os.makedirs(args.root_model, exist_ok=True)

def crossEntropy(softmax, logit, label, weight, num_classes):
    label = F.one_hot(label, num_classes=num_classes)
    target = label_smoothing(label, num_classes, delta=args.lsm)

    loss = - (weight * (target * torch.log(softmax(logit)+1e-7)).sum(dim=1)).sum()
    return loss

def disable_conv(model):
    for module in model.modules():
        if isinstance(module, nn.Conv2d):
           module.weight.requires_grad=False

def label_smoothing(y_batch_tensor, num_classes, delta):
    y_batch_smooth = (1 - delta - delta / (num_classes - 1)) * y_batch_tensor + delta / (num_classes - 1)
    return y_batch_smooth

def main():
    if args.seed is not None:
        random.seed(args.seed)
        torch.manual_seed(args.seed)
        cudnn.deterministic = True
        warnings.warn('You have chosen to seed training. '
                      'This will turn on the CUDNN deterministic setting, '
                      'which can slow down your training considerably! '
                      'You may see unexpected behavior when restarting '
                      'from checkpoints.')

    if args.gpu is not None:
        warnings.warn('You have chosen a specific GPU. This will completely '
                      'disable data parallelism.')

    if args.dist_url == "env://" and args.world_size == -1:
        args.world_size = int(os.environ["WORLD_SIZE"])

    args.distributed = args.world_size > 1 or args.multiprocessing_distributed

    ngpus_per_node = torch.cuda.device_count()
    if args.multiprocessing_distributed:
        # Since we have ngpus_per_node processes per node, the total world_size
        # needs to be adjusted accordingly
        args.world_size = ngpus_per_node * args.world_size
        # Use torch.multiprocessing.spawn to launch distributed processes: the
        # main_worker process function
        mp.spawn(main_worker, nprocs=ngpus_per_node, args=(ngpus_per_node, args))
    else:
        # Simply call main_worker function
        main_worker(args.gpu, ngpus_per_node, args)


def main_worker(gpu, ngpus_per_node, args):
    global best_acc1
    args.gpu = gpu

    if args.gpu is not None:
        print("Use GPU: {} for training".format(args.gpu))

    if args.distributed:
        if args.dist_url == "env://" and args.rank == -1:
            args.rank = int(os.environ["RANK"])
        if args.multiprocessing_distributed:
            # For multiprocessing distributed training, rank needs to be the
            # global rank among all the processes
            args.rank = args.rank * ngpus_per_node + gpu
        dist.init_process_group(backend=args.dist_backend, init_method=args.dist_url,
                                world_size=args.world_size, rank=args.rank)
    # create model
    if args.pretrained:
        print("=> using pre-trained model '{}'".format(args.arch))
        model = models.__dict__[args.arch](pretrained=True)
    else:
        print("=> creating model '{}'".format(args.arch))
        model = getattr(nets, args.arch)(gamma=args.gamma)


    if args.distributed:
        # For multiprocessing distributed, DistributedDataParallel constructor
        # should always set the single device scope, otherwise,
        # DistributedDataParallel will use all available devices.
        if args.gpu is not None:
            torch.cuda.set_device(args.gpu)
            model.cuda(args.gpu)
            # When using a single GPU per process and per
            # DistributedDataParallel, we need to divide the batch size
            # ourselves based on the total number of GPUs we have
            args.batch_size = int(args.batch_size / ngpus_per_node)
            args.workers = int((args.workers + ngpus_per_node - 1) / ngpus_per_node)
            model = torch.nn.parallel.DistributedDataParallel(model, device_ids=[args.gpu])
        else:
            model.cuda()
            # DistributedDataParallel will divide and allocate batch_size to all
            # available GPUs if device_ids are not set
            model = torch.nn.parallel.DistributedDataParallel(model)
    elif args.gpu is not None:
        torch.cuda.set_device(args.gpu)
        model = model.cuda(args.gpu)
    else:
        # DataParallel will divide and allocate batch_size to all available GPUs
        if args.arch.startswith('alexnet') or args.arch.startswith('vgg'):
            model.features = torch.nn.DataParallel(model.features)
            model.cuda()
        else:
            model = torch.nn.DataParallel(model).cuda()
            filename = args.root_model+'/model_best.pth.tar'
            if os.path.exists(filename):
                args.resume = filename

    # define loss function (criterion) and optimizer
    criterion = nn.CrossEntropyLoss().cuda(args.gpu)

    optimizer = torch.optim.SGD(model.parameters(), args.lr,
                                momentum=args.momentum,
                                weight_decay=args.weight_decay)

    # optionally resume from a checkpoint
    if args.resume:
        if os.path.isfile(args.resume):
            print("=> loading checkpoint '{}'".format(args.resume))
            if args.gpu is None:
                checkpoint = torch.load(args.resume)
            else:
                # Map model to be loaded to specified single gpu.
                loc = 'cuda:{}'.format(args.gpu)
                #checkpoint = torch.load(args.resume, map_location='cpu')
                checkpoint = torch.load(args.resume)

            args.start_epoch = checkpoint['epoch']
            best_acc1 = checkpoint['best_acc1']
            if args.gpu is not None:
                # best_acc1 may be from a checkpoint from a different GPU
                best_acc1 = best_acc1.to(args.gpu)
            model.load_state_dict(checkpoint['state_dict'])
            optimizer.load_state_dict(checkpoint['optimizer'])
            print("=> loaded checkpoint '{}' (epoch {})"
                  .format(args.resume, checkpoint['epoch']))
        else:
            print("=> no checkpoint found at '{}'".format(args.resume))

    cudnn.benchmark = True

    # Data loading code
    print(args.dataset," ",type(args.dataset))
    data=getattr(dataset,args.dataset)(batch_size=args.batch_size, num_works=args.num_works, root=args.data_path)
    train_loader=data.train
    val_loader=data.test
   
    if args.evaluate:
        validate(val_loader, model, criterion, args)
        return

    for epoch in range(args.start_epoch, args.epochs):
        if args.distributed:
            train_sampler.set_epoch(epoch)
        adjust_learning_rate(optimizer, epoch, args)

        # train for one epoch
        train(train_loader, model, criterion, optimizer, epoch, args)

        # evaluate on validation set
        acc1 = validate(val_loader, model, criterion, args)

        # remember best acc@1 and save checkpoint
        is_best = acc1 > best_acc1
        best_acc1 = max(acc1, best_acc1)

        if not args.multiprocessing_distributed or (args.multiprocessing_distributed
                and args.rank % ngpus_per_node == 0):
            save_checkpoint({
                'epoch': epoch + 1,
                'arch': args.arch,
                'state_dict': model.state_dict(),
                'best_acc1': best_acc1,
                'optimizer' : optimizer.state_dict(),
            }, is_best)


def train(train_loader, model, criterion, optimizer, epoch, args):
    batch_time = AverageMeter('Time', ':6.3f')
    data_time = AverageMeter('Data', ':6.3f')
    F_losses = AverageMeter('F_Loss', ':.4e')
    I_losses = AverageMeter('I_Loss', ':.4e')
    A_losses = AverageMeter('Loss', ':.4e')

    top1 = AverageMeter('Acc@1', ':6.2f')
    top5 = AverageMeter('Acc@5', ':6.2f')
    progress = ProgressMeter(
        len(train_loader),
        [batch_time, data_time, A_losses, top1, top5],
        prefix="Epoch: [{}]".format(epoch))


    # ResLTLoss
    def ResLTLoss(logits, labels):
        logitH, logitM, logitT = logits
        labelH, labelM = labels
        softmax = nn.Softmax(dim=1)

        # loss
        I_loss=(crossEntropy(softmax, logitH, target, labelH, args.num_classes) + crossEntropy(softmax, logitM, target, labelM, args.num_classes)) / (labelH.sum() + labelM.sum()) 
        logit = logitH + logitM
        F_loss = criterion(logit, target)
        loss= (1-args.beta) * F_loss + args.beta * I_loss
        return loss


    # switch to train mode
    model.train()
    end = time.time()
    for i, (images, target) in enumerate(train_loader):
        # measure data loading time
        data_time.update(time.time() - end)

        if args.gpu is not None:
            images = images.cuda(args.gpu, non_blocking=True)

        target = target.cuda(args.gpu, non_blocking=True)

        # compute output
        logits_list = model(images)

        ######## ResLT 
        labelH=F.one_hot(target, num_classes=args.num_classes).sum(dim=1)
        labelM=F.one_hot(target, num_classes=args.num_classes)[:,:6600].sum(dim=1)
        loss, logit = 0, 0
        for k in range(args.val_num_experts):
            loss += ResLTLoss(logits_list[k], (labelH, labelM))
            logit += logits_list[k][0] + logits_list[k][1]

        # measure accuracy and record loss
        acc1, acc5 = accuracy(logit, target, topk=(1, 5))
        top1.update(acc1[0], images.size(0))
        top5.update(acc5[0], images.size(0))
        A_losses.update(loss.detach().item(), images.size(0))

        # compute gradient and do SGD step
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # measure elapsed time
        batch_time.update(time.time() - end)
        end = time.time()

        if i % args.print_freq == 0:
            progress.display(i, args)


def validate(val_loader, model, criterion, args):
    batch_time = AverageMeter('Time', ':6.3f')
    losses = AverageMeter('Loss', ':.4e')
    top1 = AverageMeter('All_Acc@1', ':6.2f')
    top5 = AverageMeter('All_Acc@5', ':6.2f')

    progress = ProgressMeter(
        len(val_loader),
        [batch_time, losses, top1, top5],
        prefix='Test: ')

    # switch to evaluate mode
    model.eval()
    class_num=torch.zeros(8142).cuda()
    correct=torch.zeros(8142).cuda()
    with torch.no_grad():
        end = time.time()
        for i, (images, target) in enumerate(val_loader):
            if args.gpu is not None:
                images = images.cuda(args.gpu, non_blocking=True)
            target = target.cuda(args.gpu, non_blocking=True)

            # compute output
            logits_list = model(images)
            output = 0
            for i in range(args.val_num_experts):
                output += logits_list[i][0] + logits_list[i][1]
            output = output / 2 
            loss = criterion(output, target)

            # measure accuracy and record loss
            acc1, acc5 = accuracy(output, target, topk=(1, 5))
            losses.update(loss.item(), images.size(0))
            top1.update(acc1[0], images.size(0))
            top5.update(acc5[0], images.size(0))
            
            # measure elapsed time
            batch_time.update(time.time() - end)
            end = time.time()

            _, predicted = output.max(1)
            target_one_hot = F.one_hot(target, num_classes=args.num_classes)
            predict_one_hot = F.one_hot(predicted, num_classes=args.num_classes)
            class_num = class_num + target_one_hot.sum(dim=0).to(torch.float)
            correct=correct + (target_one_hot + predict_one_hot==2).sum(dim=0).to(torch.float)

            if i % args.print_freq == 0:
                progress.display(i, args)

        # TODO: this should also be done with the ProgressMeter
        acc_classes = correct / class_num
        head_acc = acc_classes[7300:].mean()
        medium_acc = acc_classes[3599:7300].mean()
        tail_acc = acc_classes[:3599].mean()
        open(args.root_model+"/train.log","a+").write((' * Acc@1 {top1.avg:.3f} Acc@5 {top5.avg:.3f} HAcc {head_acc:.3f} MAcc {medium_acc:.3f} TAcc {tail_acc:.3f} \n').format(top1=top1, top5=top5, head_acc=head_acc, medium_acc=medium_acc, tail_acc=tail_acc))

    return top1.avg


def save_checkpoint(state, is_best, filename=args.root_model+'/checkpoint.pth.tar'):
    torch.save(state, filename)
    if is_best:
        shutil.copyfile(filename, args.root_model+'/model_best.pth.tar')


class AverageMeter(object):
    """Computes and stores the average and current value"""
    def __init__(self, name, fmt=':f'):
        self.name = name
        self.fmt = fmt
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count

    def __str__(self):
        fmtstr = '{name} {val' + self.fmt + '} ({avg' + self.fmt + '})'
        return fmtstr.format(**self.__dict__)


class ProgressMeter(object):
    def __init__(self, num_batches, meters, prefix=""):
        self.batch_fmtstr = self._get_batch_fmtstr(num_batches)
        self.meters = meters
        self.prefix = prefix

    def display(self, batch, args):
        entries = [self.prefix + self.batch_fmtstr.format(batch)]
        entries += [str(meter) for meter in self.meters]
        open(args.root_model+"/train.log","a+").write('\t'.join(entries)+"\n")

    def _get_batch_fmtstr(self, num_batches):
        num_digits = len(str(num_batches // 1))
        fmt = '{:' + str(num_digits) + 'd}'
        return '[' + fmt + '/' + fmt.format(num_batches) + ']'


def adjust_learning_rate(optimizer, epoch, args):
    """Sets the learning rate to the initial LR decayed by 10 every 30 epochs"""
    lr_min = 0
    lr_max = args.lr
    if epoch < args.warmup_epochs:
       lr = args.lr / args.warmup_epochs * (epoch+1)
    else:
       lr= lr_min + 0.5 * (lr_max - lr_min) * (1 + math.cos( (epoch - args.warmup_epochs + 1) / (args.epochs - args.warmup_epochs + 1) * 3.1415926))

    for param_group in optimizer.param_groups:
        param_group['lr'] = lr


def accuracy(output, target, topk=(1,)):
    """Computes the accuracy over the k top predictions for the specified values of k"""
    with torch.no_grad():
        maxk = max(topk)
        batch_size = target.size(0)

        _, pred = output.topk(maxk, 1, True, True)
        pred = pred.t()
        correct = pred.eq(target.view(1, -1).expand_as(pred))

        res = []
        for k in topk:
            correct_k = correct[:k].view(-1).float().sum(0, keepdim=True)
            res.append(correct_k.mul_(100.0 / batch_size))
        return res


if __name__ == '__main__':
    main()