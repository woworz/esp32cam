import camera
import time


class Camera:

    # ESP32-S3 OV2640 引脚配置
    PIN_D0 = 11
    PIN_D1 = 9
    PIN_D2 = 8
    PIN_D3 = 10
    PIN_D4 = 12
    PIN_D5 = 18
    PIN_D6 = 17
    PIN_D7 = 16
    PIN_XCLK = 15    # TODO: 确认XCLK实际连接引脚
    PIN_PCLK = 13
    PIN_VSYNC = 6
    PIN_HREF = 7
    PIN_SIOD = 4     # I2C SDA
    PIN_SIOC = 5     # I2C SCL
    PIN_RESET = 14
    PIN_PWDN = -1    # 直接接GND，摄像头常开

    # 分辨率常量
    FRAMESIZE_QQVGA = 0    # 160x120
    FRAMESIZE_QVGA = 7     # 320x240
    FRAMESIZE_VGA = 8      # 400x296
    FRAMESIZE_SVGA = 9     # 480x320
    FRAMESIZE_XGA = 12     # 1024x768
    FRAMESIZE_HD = 13      # 1280x720
    FRAMESIZE_SXGA = 14    # 1280x1024
    FRAMESIZE_UXGA = 15    # 1600x1200

    def __init__(
        self,
        framesize=8,  # VGA
        quality=12,
    ):
        self.framesize = framesize
        self.quality = quality
        self._initialized = False

    def init(self):
        print("[Camera] 初始化 OV2640 (ESP32-S3) ...")
        try:
            camera.init(
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

            camera.framesize(self.framesize)
            camera.quality(self.quality)
            camera.speffect(0)   # EFFECT_NONE
            camera.whitebalance(0)  # WB_NONE
            camera.saturation(0)
            camera.brightness(0)
            camera.contrast(0)

            self._initialized = True
            time.sleep(1)
            print(f"[Camera] 初始化成功 (分辨率:{self._framesize_name()} 质量:{self.quality})")

        except Exception as e:
            print(f"[Camera] 初始化失败: {e}")
            raise

    def deinit(self):
        if self._initialized:
            camera.deinit()
            self._initialized = False

    def capture(self):
        if not self._initialized:
            self.init()
        buf = camera.capture()
        return buf

    def set_framesize(self, fs):
        self.framesize = fs
        if self._initialized:
            camera.framesize(fs)

    def set_quality(self, q):
        self.quality = q
        if self._initialized:
            camera.quality(q)

    def _framesize_name(self):
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
        }
        return names.get(self.framesize, "未知")
