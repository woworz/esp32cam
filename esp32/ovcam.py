"""
ovcam.py - OV3660 摄像头驱动模块 (ESP32-S3 专用)

本模块封装了 OV3660 摄像头的初始化、拍照、参数设置等功能。
适配 ESP32-S3-DevKitC-1 开发板，通过 DVP 并行接口连接 OV3660。

硬件连接 (ESP32-S3 <-> OV3660):
    数据线: D0=GPIO11, D1=GPIO9,  D2=GPIO8,  D3=GPIO10
            D4=GPIO12, D5=GPIO18, D6=GPIO17, D7=GPIO16
    控制线: PCLK=GPIO13, VSYNC=GPIO6, HREF=GPIO7
            XCLK=GPIO15 (时钟输出), RESET=GPIO14
    I2C:    SIOD(SDA)=GPIO4, SIOC(SCL)=GPIO5
    电源:   PWDN 直接接 GND (摄像头常开)

依赖: MicroPython camera 模块 (ESP32-S3 固件内置)
"""

import camera
import time


class Camera:
    """
    OV3660 摄像头控制类

    提供摄像头初始化、拍照、分辨率/质量设置等功能。
    所有引脚配置为类常量，修改引脚只需更改常量值。

    使用示例:
        cam = Camera(framesize=Camera.FRAMESIZE_VGA, quality=12)
        cam.init()
        img_buf = cam.capture()
        cam.deinit()
    """

    # ==================== ESP32-S3 OV3660 引脚配置 ====================
    # 数据总线 (8位并行，用于传输图像数据)
    PIN_D0 = 11     # 数据位0
    PIN_D1 = 9      # 数据位1
    PIN_D2 = 8      # 数据位2
    PIN_D3 = 10     # 数据位3
    PIN_D4 = 12     # 数据位4
    PIN_D5 = 18     # 数据位5
    PIN_D6 = 17     # 数据位6
    PIN_D7 = 16     # 数据位7

    # 时钟与同步信号
    PIN_XCLK = 15   # 外部时钟输出，ESP32-S3为OV3660提供主时钟
    PIN_PCLK = 13   # 像素时钟输入，每个时钟周期传输一个像素数据
    PIN_VSYNC = 6   # 垂直同步信号，标识一帧图像的开始
    PIN_HREF = 7    # 水平参考信号，标识一行像素数据的有效区间

    # SCCB (I2C) 配置接口，用于设置OV3660寄存器
    PIN_SIOD = 4    # SCCB 数据线 (等同 I2C SDA)
    PIN_SIOC = 5    # SCCB 时钟线 (等同 I2C SCL)

    # 控制引脚
    PIN_RESET = 14  # 摄像头复位引脚，低电平有效
    PIN_PWDN = -1   # 掉电控制，-1 表示直接接 GND，摄像头始终工作

    # ==================== 分辨率常量 ====================
    # 这些常量对应 MicroPython camera 模块的 framesize 枚举值
    # OV3660 支持最高 2048x1536 (QXGA)
    FRAMESIZE_QQVGA = 0     # 96x96      (缩略图)
    FRAMESIZE_QVGA = 7      # 320x240    (低清)
    FRAMESIZE_VGA = 8       # 400x296    (标清，推荐)
    FRAMESIZE_SVGA = 9      # 480x320    (高清)
    FRAMESIZE_XGA = 12      # 1024x768   (超清)
    FRAMESIZE_HD = 13       # 1280x720   (720P)
    FRAMESIZE_SXGA = 14     # 1280x1024  (SXGA)
    FRAMESIZE_UXGA = 15     # 1600x1200  (UXGA)
    FRAMESIZE_QXGA = 16     # 2048x1536  (QXGA，OV3660最大分辨率)

    def __init__(self, framesize=8, quality=12):
        """
        初始化摄像头参数 (不会立即启动硬件)

        参数:
            framesize (int): 分辨率，使用 FRAMESIZE_* 常量，默认 VGA (8)
            quality (int): JPEG 压缩质量，范围 0-63，值越小质量越高，默认 12
        """
        self.framesize = framesize
        self.quality = quality
        self._initialized = False  # 硬件初始化状态标志

    def init(self):
        """
        初始化 OV3660 摄像头硬件

        调用 MicroPython camera.init() 并传入所有引脚配置。
        初始化后设置分辨率、质量、图像效果等参数。

        异常:
            Exception: 摄像头初始化失败 (引脚冲突、硬件连接问题等)
        """
        print("[Camera] 初始化 OV3660 (ESP32-S3) ...")
        try:
            # 调用底层 camera 模块初始化，传入 DVP 接口全部引脚
            camera.init(
                0,
                d0=self.PIN_D0,
                d1=self.PIN_D1,
                d2=self.PIN_D2,
                d3=self.PIN_D3,
                d4=self.PIN_D4,
                d5=self.PIN_D5,
                d6=self.PIN_D6,
                d7=self.PIN_D7,
                xclk=self.PIN_XCLK,
                pclk=self.PIN_PCLK,
                vsync=self.PIN_VSYNC,
                href=self.PIN_HREF,
                sda=self.PIN_SIOD,
                scl=self.PIN_SIOC,
                reset=self.PIN_RESET,
                pwdn=self.PIN_PWDN,
            )

            # 设置图像参数
            camera.framesize(self.framesize)     # 分辨率
            camera.quality(self.quality)         # JPEG 质量
            camera.speffect(0)                   # 特效: 0=无特效
            camera.whitebalance(0)               # 白平衡: 0=关闭自动
            camera.saturation(0)                 # 饱和度: 0=默认
            camera.brightness(0)                 # 亮度: 0=默认
            camera.contrast(0)                   # 对比度: 0=默认

            self._initialized = True
            time.sleep(1)  # 等待摄像头稳定
            print(f"[Camera] 初始化成功 (分辨率:{self._framesize_name()} 质量:{self.quality})")

        except Exception as e:
            print(f"[Camera] 初始化失败: {e}")
            raise

    def deinit(self):
        """
        释放摄像头硬件资源

        释放后可重新调用 init() 初始化。
        """
        if self._initialized:
            camera.deinit()
            self._initialized = False
            print("[Camera] 已释放")

    def capture(self):
        """
        拍摄一张照片

        返回 JPEG 格式的图像数据 (bytes)。
        如果摄像头未初始化，会自动调用 init()。

        返回:
            bytes: JPEG 图像数据，失败返回 None
        """
        if not self._initialized:
            self.init()
        buf = camera.capture()
        return buf

    def set_framesize(self, fs):
        """
        动态修改分辨率

        参数:
            fs (int): 新的分辨率值，使用 FRAMESIZE_* 常量
        """
        self.framesize = fs
        if self._initialized:
            camera.framesize(fs)

    def set_quality(self, q):
        """
        动态修改 JPEG 压缩质量

        参数:
            q (int): 新的质量值 (0-63)，值越小质量越高
        """
        self.quality = q
        if self._initialized:
            camera.quality(q)

    def _framesize_name(self):
        """返回当前分辨率的可读名称 (内部方法)"""
        names = {
            0: "96x96",
            1: "128x128",
            2: "160x120",
            4: "176x144",
            5: "240x176",
            6: "240x240",
            7: "320x240",
            8: "400x296",
            9: "480x320",
            10: "640x480",
            11: "800x600",
            12: "1024x768",
            13: "1280x720",
            14: "1280x1024",
            15: "1600x1200",
            16: "2048x1536",
        }
        return names.get(self.framesize, "未知")
