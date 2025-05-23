import os
import torch

from setuptools import setup
from torch.utils.cpp_extension import BuildExtension, CUDAExtension

cxx_args = ['-std=c++11']

nvcc_args = [
    # '-gencode', 'arch=compute_60,code=sm_60',
    # '-gencode', 'arch=compute_61,code=sm_61',
    # '-gencode', 'arch=compute_70,code=sm_70',
    # '-gencode', 'arch=compute_70,code=compute_70'
    '-gencode', 'arch=compute_86,code=sm_86'
]

setup(
    name='adaptive_gridsampler_cuda',
    ext_modules=[
        CUDAExtension('adaptive_gridsampler_cuda', ['adaptive_gridsampler_cuda.cpp', 'adaptive_gridsampler_kernel.cu'], extra_compile_args={'cxx': cxx_args, 'nvcc': nvcc_args})
    ],
    cmdclass={'build_ext': BuildExtension}
)


