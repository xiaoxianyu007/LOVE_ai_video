"""
utils/depth.py — CPU 伪深度图生成（零 GPU 依赖）
============================================
关键设计：
  1. 径向近景（中心近、边缘远）
  2. 垂直近景（下方近、上方远）
  3. 加微量噪声避免平坦
"""
import numpy as np
import cv2


def make_pseudo_depth(image, seed=0):
    """
    根据输入图像尺寸生成 CPU 伪深度图。
    返回 float32 [0, 1]，1.0=近景，0.0=远景。
    """
    if isinstance(image, str):
        img = cv2.imread(image)
        h, w = img.shape[:2]
    else:
        h, w = image.shape[:2]

    yg, xg = np.mgrid[0:h, 0:w].astype(np.float32)

    # 焦点偏下 55%（人眼自然注视点）
    dist = np.sqrt((xg - w/2)**2 + (yg - h*0.55)**2)
    dist_n = dist / dist.max()
    radial = 1.0 - dist_n  # 中心近、边缘远

    # 垂直梯度（下方近、上方远）
    vertical = 1.0 - yg / h

    # 合成：径向 60% + 垂直 40%
    depth = radial * 0.6 + vertical * 0.4

    # 噪声
    rng = np.random.default_rng(seed)
    depth += rng.random((h, w), dtype=np.float32) * 0.04

    return np.clip(depth, 0.0, 1.0).astype(np.float32)


def preprocess(depth_raw, gamma=0.6, amp=0.4):
    """
    深度图标准化：smooth → 归一化 → gamma → 振幅。
    返回 0~amp 的位移系数矩阵。
    """
    d = cv2.GaussianBlur(depth_raw, (3, 3), 0.3)
    d_min, d_max = d.min(), d.max()
    if d_max - d_min > 1e-6:
        d = (d - d_min) / (d_max - d_min)
    d = np.clip(d, 0.0, 1.0) ** gamma
    d_min2, d_max2 = d.min(), d.max()
    if d_max2 - d_min2 > 0.01:
        d = (d - d_min2) / (d_max2 - d_min2)
    return d * amp
