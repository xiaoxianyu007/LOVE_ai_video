"""
utils/parallax.py — 2.5D 视差视频渲染（纯 CPU remap）
==============================================
核心公式：mx = x - depth * ramp * AMP * w
         my = y - depth * ramp * AMP * h

ramp 采用 cubic ease-out 曲线：1-(1-t)³，起步快、动效明显
不再使用 sin 振荡，所有动效单向运动，动完即停。

7 种业界经典动效（参考 Ken Burns / 3D Parallax / AE 2.5D）：
  1. sweep_right  — 水平右扫 + 推入（Ken Burns 经典横移）
  2. sweep_left   — 水平左扫 + 推入
  3. push_in      — 纯推进（Ken Burns 经典缩放）
  4. rise         — 缓慢上浮 + 推入（纪录片上升镜头）
  5. drift_diagonal — 对角漂移 + 推入
  6. dolly_zoom   — 拉远 + 深度错觉（眩晕镜头 / Vertigo Effect）
  7. focus_right  — 向右聚焦 + 推入（引导视线）
"""
import math
import os
import subprocess

import cv2
import numpy as np
from loguru import logger

from config import (
    PARALLAX_X, PARALLAX_Y, ZOOM_AMP, DEPTH_GAMMA, DEPTH_AMP,
    FPS, RES_W, RES_H, CRF, PRESET, MOTIONS, FFMPEG_PATH,
)
from utils.depth import make_pseudo_depth, preprocess


def _cubic_ease_out(t):
    """cubic ease-out 曲线：1-(1-t)³，起步快、动效明显，到终点自然停止。"""
    return 1.0 - (1.0 - t) ** 3


def make_motion_map(t, depth_pow, w, h, motion):
    """
    根据进度 t (0→1) 计算 remap 用的 mx/my。

    所有 motion 都使用 cubic ease-out 单向 ramp，只往一个方向动，动完停止。
    """
    x, y = np.meshgrid(np.arange(w, dtype=np.float32),
                       np.arange(h, dtype=np.float32))
    cx, cy = w / 2.0, h / 2.0

    ramp = _cubic_ease_out(t)

    # ── 7 种业界经典动效（仅 sweep_left/right 降低70%，其余恢复原始值）──
    if motion == "sweep_right":
        # Ken Burns 经典：水平右扫 + 缩放推入（降低70%）
        sx, sy = ramp * 0.6, 0.0
        zoom_eff = 1.0 + depth_pow * ramp * ZOOM_AMP * 0.36
    elif motion == "sweep_left":
        # 水平左扫 + 缩放推入（降低70%）
        sx, sy = -ramp * 0.6, 0.0
        zoom_eff = 1.0 + depth_pow * ramp * ZOOM_AMP * 0.36
    elif motion == "push_in":
        # 纯推进（Ken Burns 经典缩放）
        sx, sy = 0.0, 0.0
        zoom_eff = 1.0 + depth_pow * ramp * ZOOM_AMP * 1.2
    elif motion == "rise":
        # 纪录片上升镜头：缓慢上浮 + 轻微推入
        sx, sy = 0.0, -ramp * 0.6
        zoom_eff = 1.0 + depth_pow * ramp * ZOOM_AMP * 0.6
    elif motion == "drift_diagonal":
        # 对角漂移 + 推入
        sx, sy = ramp * 0.8, ramp * 0.5
        zoom_eff = 1.0 + depth_pow * ramp * ZOOM_AMP * 0.7
    elif motion == "dolly_zoom":
        # 眩晕镜头（Vertigo Effect）：拉远 + 深度错觉
        sx, sy = 0.0, 0.0
        zoom_eff = 1.0 - depth_pow * ramp * ZOOM_AMP * 0.5
    elif motion == "focus_right":
        # 向右聚焦 + 推入：引导视线向右，同时放大主体
        sx, sy = ramp * 0.7, ramp * 0.15
        zoom_eff = 1.0 + depth_pow * ramp * ZOOM_AMP * 0.9
    else:
        # 默认：水平右扫
        sx, sy = ramp, 0.0
        zoom_eff = 1.0 + depth_pow * ramp * ZOOM_AMP * 0.8

    # 视差位移
    mx = x - depth_pow * sx * PARALLAX_X * w
    my = y - depth_pow * sy * PARALLAX_Y * h

    # 缩放（以图像中心为锚点）
    mx = (mx - cx) / zoom_eff + cx
    my = (my - cy) / zoom_eff + cy

    return mx.astype(np.float32), my.astype(np.float32)


def render(image_path, duration, out_path, motion="sweep_right"):
    """
    渲染单段视差视频。
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"无法读取: {image_path}")
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h_img, w_img = img_rgb.shape[:2]

    # 深度图
    depth_raw = make_pseudo_depth(img_rgb, seed=hash(image_path) & 0xFFFF)
    depth_pow = preprocess(depth_raw, DEPTH_GAMMA, DEPTH_AMP)

    n_frames = max(1, int(duration * FPS))

    cmd = [
        FFMPEG_PATH, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{RES_W}x{RES_H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", PRESET, "-crf", str(CRF), "-r", str(FPS),
        out_path
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(n_frames):
            t = i / max(n_frames - 1, 1)
            mx, my = make_motion_map(t, depth_pow, w_img, h_img, motion)
            cv2.ocl.setUseOpenCL(False)
            warped = cv2.remap(img_rgb, mx, my, cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REFLECT_101)
            warped = cv2.resize(warped, (RES_W, RES_H), interpolation=cv2.INTER_LINEAR)
            try:
                proc.stdin.write(warped.tobytes())
            except BrokenPipeError:
                logger.warning(f"  ffmpeg pipe 提前断开 (第{i}/{n_frames}帧)")
                break
    finally:
        try: proc.stdin.close()
        except OSError: pass
        ret = proc.wait(timeout=300)
        if ret != 0:
            raise RuntimeError(f"ffmpeg 退出码 {ret}, 输出可能损坏: {out_path}")

    logger.info(f"  ✓ 视差: {out_path} ({n_frames}帧, {motion}, cubic-ease-out单向)")