"""
tft_display.py - ST7789 TFT 显示屏驱动模块 (ESP32-S3 专用)

本模块封装了 ST7789 TFT 显示屏的初始化、图像显示等功能。
适配 ESP32-S3-DevKitC-1 开发板，通过 SPI 接口连接 1.8 寸 TFT 屏幕 (240x320)。

硬件连接 (ESP32-S3 <-> ST7789 TFT):
    SPI:    SCK=GPIO39,  SDA(MOSI)=GPIO38
    控制:   CS=GPIO37,   DC=GPIO36,  RST=GPIO35
    电源:   BL=GPIO40 (背光), VCC=3.3V (必须接3.3V! 不要接5V), GND=GND

依赖: MicroPython machine 模块 (ESP32-S3 固件内置)
"""

import machine
import time
import struct


class ST7789:
    """
    ST7789 TFT 显示屏控制类

    提供显示屏初始化、图像显示、背光控制等功能。
    支持 RGB565 格式的图像数据。

    使用示例:
        tft = ST7789()
        tft.init()
        tft.fill(0x0000)  # 黑色背景
        tft.show_image(img_data, 0, 0, 240, 320)
        tft.deinit()
    """

    # ==================== ESP32-S3 ST7789 引脚配置 ====================
    PIN_SCK = 39     # SPI 时钟
    PIN_SDA = 38     # SPI 数据 (MOSI)
    PIN_CS = 37      # 片选
    PIN_DC = 36      # 数据/命令选择
    PIN_RST = 35     # 复位
    PIN_BL = 40      # 背光控制

    # ==================== ST7789 命令 ====================
    CMD_NOP = 0x00
    CMD_SWRESET = 0x01
    CMD_SLPOUT = 0x11
    CMD_NORON = 0x13
    CMD_INVON = 0x21
    CMD_DISPON = 0x29
    CMD_CASET = 0x2A
    CMD_RASET = 0x2B
    CMD_RAMWR = 0x2C
    CMD_MADCTL = 0x36
    CMD_COLMOD = 0x3A

    # ==================== 显示参数 ====================
    WIDTH = 240
    HEIGHT = 320

    def __init__(self):
        """
        初始化 TFT 显示屏参数 (不会立即启动硬件)
        """
        self._initialized = False
        self.spi = None
        self.bl_pin = None

    def init(self):
        """
        初始化 ST7789 TFT 显示屏硬件

        配置 SPI 接口，发送初始化命令序列。

        异常:
            Exception: 显示屏初始化失败
        """
        print("[TFT] 初始化 ST7789 (240x320) ...")
        try:
            # 初始化 SPI 接口
            self.spi = machine.SPI(
                1,  # SPI1
                baudrate=40000000,  # 40MHz
                polarity=0,
                phase=0,
                sck=machine.Pin(self.PIN_SCK),
                mosi=machine.Pin(self.PIN_SDA),
            )

            # 初始化控制引脚
            self.cs_pin = machine.Pin(self.PIN_CS, machine.Pin.OUT, value=1)
            self.dc_pin = machine.Pin(self.PIN_DC, machine.Pin.OUT, value=0)
            self.rst_pin = machine.Pin(self.PIN_RST, machine.Pin.OUT, value=1)
            self.bl_pin = machine.Pin(self.PIN_BL, machine.Pin.OUT, value=1)

            # 硬件复位
            self.rst_pin.value(0)
            time.sleep(0.02)
            self.rst_pin.value(1)
            time.sleep(0.12)

            # 发送初始化命令序列
            self._write_cmd(self.CMD_SWRESET)  # 软件复位
            time.sleep(0.15)
            self._write_cmd(self.CMD_SLPOUT)   # 退出睡眠模式
            time.sleep(0.05)

            # 设置像素格式: 16bit RGB565
            self._write_cmd(self.CMD_COLMOD)
            self._write_data(0x55)  # 16bit

            # 设置内存访问控制 (横屏)
            self._write_cmd(self.CMD_MADCTL)
            self._write_data(0x70)  # MX + MV + MY (横屏)

            # 开启显示
            self._write_cmd(self.CMD_INVON)    # 颜色反转 (取决于屏幕模块)
            self._write_cmd(self.CMD_NORON)    # 正常显示模式
            self._write_cmd(self.CMD_DISPON)   # 开启显示
            time.sleep(0.05)

            self._initialized = True
            print("[TFT] 初始化成功 (240x320, RGB565)")

        except Exception as e:
            print(f"[TFT] 初始化失败: {e}")
            raise

    def deinit(self):
        """
        释放显示屏硬件资源
        """
        if self._initialized:
            if self.spi:
                self.spi.deinit()
            self._initialized = False
            print("[TFT] 已释放")

    def _write_cmd(self, cmd):
        """发送命令字节"""
        self.dc_pin.value(0)
        self.cs_pin.value(0)
        self.spi.write(bytes([cmd]))
        self.cs_pin.value(1)

    def _write_data(self, data):
        """发送数据字节"""
        self.dc_pin.value(1)
        self.cs_pin.value(0)
        if isinstance(data, int):
            self.spi.write(bytes([data]))
        else:
            self.spi.write(data)
        self.cs_pin.value(1)

    def _set_window(self, x0, y0, x1, y1):
        """设置显示窗口"""
        self._write_cmd(self.CMD_CASET)
        self._write_data(struct.pack(">HH", x0, x1))
        self._write_cmd(self.CMD_RASET)
        self._write_data(struct.pack(">HH", y0, y1))
        self._write_cmd(self.CMD_RAMWR)

    def fill(self, color):
        """
        用指定颜色填充整个屏幕

        参数:
            color (int): RGB565 格式的颜色值
        """
        if not self._initialized:
            return
        self._set_window(0, 0, self.WIDTH - 1, self.HEIGHT - 1)
        self.dc_pin.value(1)
        self.cs_pin.value(0)
        # 批量发送颜色数据
        color_bytes = struct.pack(">H", color)
        self.spi.write(color_bytes * (self.WIDTH * self.HEIGHT))
        self.cs_pin.value(1)

    def show_image(self, img_data, x, y, width, height):
        """
        在指定位置显示图像

        参数:
            img_data (bytes): RGB565 格式的图像数据
            x (int): 左上角 X 坐标
            y (int): 左上角 Y 坐标
            width (int): 图像宽度
            height (int): 图像高度
        """
        if not self._initialized:
            return
        # 边界检查
        if x < 0 or y < 0 or x + width > self.WIDTH or y + height > self.HEIGHT:
            return
        self._set_window(x, y, x + width - 1, y + height - 1)
        self.dc_pin.value(1)
        self.cs_pin.value(0)
        self.spi.write(img_data)
        self.cs_pin.value(1)

    def show_jpeg(self, jpeg_data, x, y):
        """
        显示 JPEG 图像 (需要 JPEG 解码支持)

        注意: MicroPython 默认不支持 JPEG 解码，
        需要使用 JPEG 库或在服务器端转换为 RGB565 格式。

        参数:
            jpeg_data (bytes): JPEG 格式的图像数据
            x (int): 左上角 X 坐标
            y (int): 左上角 Y 坐标
        """
        # 占位实现 - 实际需要 JPEG 解码库
        print("[TFT] JPEG 显示需要解码库支持")

    def set_backlight(self, on):
        """
        控制背光开关

        参数:
            on (bool): True=开, False=关
        """
        if self.bl_pin:
            self.bl_pin.value(1 if on else 0)

    def show_text(self, text, x, y, color=0xFFFF, size=1):
        """
        在指定位置显示文本 (简单点阵字体)

        参数:
            text (str): 要显示的文本
            x (int): X 坐标
            y (int): Y 坐标
            color (int): RGB565 格式的文本颜色
            size (int): 字体大小倍数 (1=8x16, 2=16x32)
        """
        # 占位实现 - 实际需要字体数据
        print(f"[TFT] 显示文本: {text}")
