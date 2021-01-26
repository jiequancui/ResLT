# ResLT: Residual Learning for Long-tailed Recognition
The code for paper "ResLT: Residual Learning for Long-tailed Recognition" will release soon.


Abstract:
Deep learning algorithms face great challenges with long-tailed data distribution which, however, is quite a common case in real-world scenarios. Previous methods tackle the problem from either the aspect of input space (re-sampling classes with different frequencies) or loss space (re-weighting classes with different weights), suffering from heavy over-fitting to tail classes or hard optimization during training. To alleviate these issues, we propose a more fundamental perspective for long-tailed recognition, {\it i.e.}, from the aspect of parameter space, and aims to preserve specific capacity for classes with low frequencies. From this perspective, the trivial solution utilizes different branches for the head, medium, tail classes respectively, and then sums their outputs as the final results is not feasible. Instead, we design the effective residual fusion mechanism -- with one main branch optimized to recognize images from all classes, another two residual branches are gradually fused and optimized to enhance images from medium+tail classes and tail classes respectively. Then the branches are aggregated into final results by additive shortcuts. We test our method on several benchmarks, {\it i.e.}, long-tailed version of CIFAR-10, CIFAR-100, Places, ImageNet, and iNaturalist 2018. Experimental results manifest that our method achieves new state-of-the-art for long-tailed recognition. Code will be available at \url{https://github.com/FPNAS/ResLT}.



