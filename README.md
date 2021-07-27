# ResLT: Residual Learning for Long-tailed Recognition
This repository contains the implementation code for paper:  
**Residual Learning for Long-tailed Recognition** https://arxiv.org/abs/2101.10633    
  
If you find this code or idea useful, please consider citing our work:
```
@article{cui2021reslt,
  title={ResLT: Residual Learning for Long-tailed Recognition},
  author={Cui, Jiequan and Liu, Shu and Tian, Zhuotao and Zhong, Zhisheng and Jia, Jiaya},
  journal={arXiv preprint arXiv:2101.10633},
  year={2021}
}
```  

# Overview
In this paper, we proposed a residual learning method to address long-tailed recognition, which contains a **Residual Fusion Module** and a **Parameter Specialization Mechanism**.
With extensive ablation studies, we demonstrate the effectiveness of our method.  

![image](https://github.com/FPNAS/ResLT/blob/main/assets/reslt.jpg)

# Get Started
## ResLT Training
For CIFAR, due to the small data size, different experimental environment can have a big difference. To achieve the reported results, you may need to slightly tune the $\alpha$.
```
bash sh/CIFAR100/CIFAR100LT_imf0.01_resnet32sx1_beta0.9950.sh
```
For ImageNet-LT,

```
bash sh/X50.sh
```

For iNaturalist 2018,

```
bash sh/R50.sh
```

## Results and Models
### CIFAR
Model | Download
---- | ---
CIFAR-10-imb0.01 | -
CIFAR-10-imb0.02 | -
CIFAR-10-imb0.1  | -
CIFAR-100-imb0.01 | -
CIFAR-100-imb0.02 | -
CIFAR-100-imb0.1  | -

### ImageNet-LT
Model | Download
---- | ---
ResNet-10   | -
ResNeXt-50  | -
ResNeXt-101 | -

### iNatualist 2018
Model | Download
---- | ----
ResNet-50 | -

### Places-LT
Model | Download
---- | ----
ResNet-152 | -

# Acknowledgements
This code is partly based on the open-source implementations from offical PyTorch examples and [LDAM-DRW](https://github.com/kaidic/LDAM-DRW).

# Contact
If you have any questions, feel free to contact us through email (jiequancui@link.cuhk.edu.hk) or Github issues. Enjoy!











