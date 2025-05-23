import math
import torch
import torch.nn as nn
from utils.util import opt_get
#
#
def default_conv(in_channels, out_channels, kernel_size, bias=True):
    return nn.Conv2d(
        in_channels, out_channels, kernel_size,
        padding=(kernel_size // 2), bias=bias)


class EDSR(nn.Module):

    def __init__(self, opt=None, n_resblocks=32, n_feats=256, scale=4, conv=default_conv):
        super(EDSR, self).__init__()
        self.opt = opt

        n_resblocks = opt_get(opt, ['network_G', 'n_resblocks'], 32)
        n_feats = opt_get(opt, ['network_G', 'n_feats'], 256)
        res_scale = opt_get(opt, ['network_G', 'res_scale'], 0.1)
        scale = opt_get(opt, ['network_G', 'scale'], 4)
        rgb_range = opt_get(opt, ['network_G', 'rgb_range'], 1)
        n_colors = opt_get(opt, ['network_G', 'n_colors'], 3)
        kernel_size = 3

        act = nn.ReLU(True)

        self.sub_mean = MeanShift(rgb_range)
        self.add_mean = MeanShift(rgb_range, sign=1)

        # define head module
        m_head = [conv(n_colors, n_feats, kernel_size)]

        # define body module
        m_body = [
            ResBlock(
                conv, n_feats, kernel_size, act=act, res_scale=res_scale
            ) for _ in range(n_resblocks)
        ]
        m_body.append(conv(n_feats, n_feats, kernel_size))

        # define tail module
        m_tail = [
            Upsampler(conv, scale, n_feats, act=False),
            conv(n_feats, n_colors, kernel_size)
        ]

        self.head = nn.Sequential(*m_head)
        self.body = nn.Sequential(*m_body)
        self.tail = nn.Sequential(*m_tail)

    def forward(self, x):
        # x = self.sub_mean(x) ##car-edsr

        x = self.head(x)
        res = self.body(x)
        res += x
        x = self.tail(res)

        # x = self.add_mean(x) ##car-edsr

        return x


class MeanShift(nn.Conv2d):
    def __init__(
            self, rgb_range,
            rgb_mean=(0.4488, 0.4371, 0.4040), rgb_std=(1.0, 1.0, 1.0), sign=-1):
        super(MeanShift, self).__init__(3, 3, kernel_size=1)
        std = torch.Tensor(rgb_std)
        self.weight.data = torch.eye(3).view(3, 3, 1, 1) / std.view(3, 1, 1, 1)
        self.bias.data = sign * rgb_range * torch.Tensor(rgb_mean) / std
        for p in self.parameters():
            p.requires_grad = False


class BasicBlock(nn.Sequential):
    def __init__(
            self, conv, in_channels, out_channels, kernel_size, stride=1, bias=False,
            bn=True, act=nn.ReLU(True)):

        m = [conv(in_channels, out_channels, kernel_size, bias=bias)]
        if bn:
            m.append(nn.BatchNorm2d(out_channels))
        if act is not None:
            m.append(act)

        super(BasicBlock, self).__init__(*m)


class ResBlock(nn.Module):
    def __init__(
            self, conv, n_feats, kernel_size,
            bias=True, bn=False, act=nn.ReLU(True), res_scale=1):

        super(ResBlock, self).__init__()
        m = []
        for i in range(2):
            m.append(conv(n_feats, n_feats, kernel_size, bias=bias))
            if bn:
                m.append(nn.BatchNorm2d(n_feats))
            if i == 0:
                m.append(act)

        self.body = nn.Sequential(*m)
        self.res_scale = res_scale

    def forward(self, x):
        res = self.body(x).mul(self.res_scale)
        res += x

        return res


class Upsampler(nn.Sequential):
    def __init__(self, conv, scale, n_feats, bn=False, act=False, bias=True):

        m = []
        if (scale & (scale - 1)) == 0:  # Is scale = 2^n?
            for _ in range(int(math.log(scale, 2))):
                m.append(conv(n_feats, 4 * n_feats, 3, bias))
                m.append(nn.PixelShuffle(2))
                if bn:
                    m.append(nn.BatchNorm2d(n_feats))
                if act == 'relu':
                    m.append(nn.ReLU(True))
                elif act == 'prelu':
                    m.append(nn.PReLU(n_feats))

        elif scale == 3:
            m.append(conv(n_feats, 9 * n_feats, 3, bias))
            m.append(nn.PixelShuffle(3))
            if bn:
                m.append(nn.BatchNorm2d(n_feats))
            if act == 'relu':
                m.append(nn.ReLU(True))
            elif act == 'prelu':
                m.append(nn.PReLU(n_feats))
        else:
            raise NotImplementedError

        super(Upsampler, self).__init__(*m)



# import math
#
# from torch import nn
#
# '''
#     原因：为了进行数据特征标准化，即像机器学习中的特征预处理那样对输入特征向量各维去均值再除以标准差，
#     但由于自然图像各点像素值的范围都在0-255之间，方差大致一样，
#     只要做去均值（减去整个图像数据集的均值或各通道关于图像数据集的均值）处理即可
#
#     相当于做一次图像预处理
# '''
#
#
# class MeanShift(nn.Conv2d):
#     def __init__(self, rgb_range, rgb_mean=(0.4488, 0.4371, 0.4040), rgb_std=(1.0, 1.0, 1.0), sign=-1):
#         super(MeanShift, self).__init__(3, 3, kernel_size=(1, 1))
#         std = torch.Tensor(rgb_std)
#         self.weight.data = torch.eye(3).view(3, 3, 1, 1) / std.view(3, 1, 1, 1)
#         self.bias.data = sign * rgb_range * torch.Tensor(rgb_mean) / std
#
#         for p in self.parameters():
#             p.requires_grad = False
#
#
# '''
#     for bias:
#         CLASS torch.nn.Conv2d(in_channels, out_channels,
#                               kernel_size, stride=1, padding=0, dilation=1, groups=1, bias=True, padding_mode='zeros')
#
#         padding='valid' is the same as no padding.
#         padding='same' pads the input so the output has the shape as the input.
#         However, this mode doesn’t support any stride values other than 1.
#
#
#         bias (bool, optional) – If True, adds a learnable bias to the output. Default: True
#
#
# '''
#
# '''
#     according to the paper, they use res_scale=0.1 to set the res_block because:
#
#     `EDSR` 的残差缩放 `Residual Scaling`
#
#
#     EDSR 的作者认为提高网络模型性能的最简单方法是增加参数数量，堆叠的方式是在卷积神经网络中，堆叠多个层或通过增加滤波器的数量。
#     当考虑有限的复合资源时，增加宽度 (特征Channels的数量) F 而不是深度(层数) B 来最大化模型容量。
#     但是特征图的数量增加(太多的残差块)到一定水平以上会使训练过程在数值上不稳定。
#     残差缩放 (residual scaling) 即残差块在相加前，经过卷积处理的一路乘以一个小数 (作者用了0.1)。
#     在每个残差块中，在最后的卷积层之后放置恒定的缩放层。
#     当使用大量滤波器时，这些模块极大地稳定了训练过程。
#     在测试阶段，该层可以集成到之前的卷积层中，以提高计算效率。
#     使用上面三种网络对比图中提出的残差块（即结构类似于 SRResNet ，但模型在残差块之外没有 ReLU** 层）构建单尺度模型 EDSR。
#     此外，因为每个卷积层仅使用 64 个特征图，所以单尺度模型没有残差缩放层。
# '''
#
#
# class ResBlock(nn.Module):
#     def __init__(self, n_feats, kernel_size, padding, bias=False, bn=False, act=nn.ReLU(inplace=True), res_scale=0.1):
#         super(ResBlock, self).__init__()
#         m = []
#
#         for i in range(2):
#             m.append(nn.Conv2d(in_channels=n_feats, out_channels=n_feats,
#                                kernel_size=kernel_size, padding=padding, bias=bias))
#             if bn:
#                 m.append(nn.BatchNorm2d(n_feats))
#             if i == 0:
#                 m.append(act)
#
#         self.body = nn.Sequential(*m)
#         self.res_scale = res_scale
#
#     def forward(self, x):
#         res = self.body(x).mul(self.res_scale)
#         res += x
#         return res
#
#
# class Upsampler(nn.Sequential):
#     def __init__(self, scale, n_feats, bn=False, act=False, bias=False):
#         m = []
#         '''
#             &是按位逻辑运算符，比如5 & 6，5和6转换为二进制是101和110，此时101 & 110=100，100转换为十进制是4，所以5 & 6=4
#
#
#             如果一个数是2^n，说明这个二进制里面只有一个1。除了1.
#             a  = (10000)b
#             a-1 = (01111)b
#             a&(a-1) = 0。
#             如果一个数不是2^n，
#             说明它的二进制里含有多一个1。
#             a = (1xxx100)b
#             a-1=(1xxx011)b
#             那么 a&(a-1)就是 (1xxx000)b，
#             而不会为0。
#
#             所以可以用这种方法判断一个数是不2^n。
#
#         '''
#
#         '''
#             一：与运算符（&）
#             运算规则：
#             0&0=0；0&1=0；1&0=0；1&1=1
#             即：两个同时为1，结果为1，否则为0
#         '''
#
#         if (scale & (scale - 1)) == 0:  # Is scale = 2^n?
#             for _ in range(int(math.log(scale, 2))):
#                 m.append(nn.Conv2d(in_channels=n_feats, out_channels=4 * n_feats,
#                                    kernel_size=(3, 3), padding=(1, 1), bias=bias))
#                 m.append(nn.PixelShuffle(2))
#                 if bn:
#                     m.append(nn.BatchNorm2d(n_feats))
#                 if act == 'relu':
#                     m.append(nn.ReLU(True))
#                 elif act == 'prelu':
#                     m.append(nn.PReLU(n_feats))
#
#         elif scale == 3:
#             m.append(nn.Conv2d(in_channels=n_feats, out_channels=9 * n_feats,
#                                kernel_size=(3, 3), padding=(1, 1), bias=bias))
#             m.append(nn.PixelShuffle(3))
#             if bn:
#                 m.append(nn.BatchNorm2d(n_feats))
#             if act == 'relu':
#                 m.append(nn.ReLU(True))
#             elif act == 'prelu':
#                 m.append(nn.PReLU(n_feats))
#
#         else:
#             raise NotImplementedError
#
#         super(Upsampler, self).__init__(*m)
#
#
#
# class EDSR(nn.Module):
#     def __init__(self,
#                  opt = None,
#                  n_channels=3,
#                  n_resblocks=32,
#                  n_feats=256,
#                  scale=4,
#                  res_scale=0.1,
#                  rgb_range=1
#                  ):
#         #                  num_in_ch,
#         #                  num_out_ch,
#         #                  num_feat=64,
#         #                  num_block=16,
#         #                  upscale=4,
#         #                  res_scale=1,
#         #                  img_range=255.,
#         #                  rgb_mean=(0.4488, 0.4371, 0.4040)):
#
#         super(EDSR, self).__init__()
#
#         self.n_channels = n_channels
#         self.n_resblocks = n_resblocks
#         self.n_feats = n_feats
#         self.scale = scale
#         self.res_scale = res_scale
#         self.rgb_range = rgb_range
#
#         self.kernel_size = (3, 3)
#         self.padding = (1, 1)
#         self.act = nn.ReLU(True)
#
#         # self.sub_mean = MeanShift(self.rgb_range)
#         # self.add_mean = MeanShift(self.rgb_range, sign=1)
#
#         net_head = [nn.Conv2d(self.n_channels, self.n_feats, kernel_size=self.kernel_size, padding=self.padding)]
#
#         net_body = [
#             ResBlock(
#                 n_feats=self.n_feats, kernel_size=self.kernel_size, padding=self.padding,
#                 act=self.act, res_scale=self.res_scale
#             ) for _ in range(self.n_resblocks)
#         ]
#
#         net_body.append(nn.Conv2d(in_channels=self.n_feats, out_channels=self.n_feats,
#                                   kernel_size=self.kernel_size, padding=self.padding))
#
#         net_tail = [
#             Upsampler(self.scale, self.n_feats, act=False),
#             nn.Conv2d(in_channels=self.n_feats, out_channels=self.n_channels,
#                       kernel_size=self.kernel_size, padding=self.padding)
#         ]
#
#         self.net_head = nn.Sequential(*net_head)
#         self.net_body = nn.Sequential(*net_body)
#         self.net_tail = nn.Sequential(*net_tail)
#
#
#
#
#     def forward(self, x):
#         # x = self.sub_mean(x)
#         x = self.net_head(x)
#
#         res = self.net_body(x)
#         res = torch.add(x, res)
#
#         x = self.net_tail(res)
#         # x = self.add_mean(x)
#
#         return x
