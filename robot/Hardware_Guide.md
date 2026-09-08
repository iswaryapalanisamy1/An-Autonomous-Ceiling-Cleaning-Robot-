# Hardware Integration Guide: Ceiling Cleaning Robot

This guide explains how to connect your ESP32-CAM and STM32 hardware to the real-time web dashboard.

## 1. Updated ESP32-CAM Code

I have modified the code you dumped into your ESP32. Your original code handled the camera stream perfectly, but it was missing two things needed to talk to the dashboard and the STM32:
1. **CORS support** (so the dashboard can communicate with the ESP32).
2. **Action API** (to receive dashboard button clicks and send them to the STM32 via Serial).

Copy and paste this **updated code** into your Arduino IDE and flash it to your ESP32-CAM:

```cpp
#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"

// ✅ Fix brownout issue (important for ESP32-CAM)
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// 🔐 WiFi credentials
const char* ssid = "iot5";
const char* password = "123456789";

// 📷 AI Thinker ESP32-CAM pins
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

httpd_handle_t stream_httpd = NULL;

// Use HardwareSerial for STM32 Communication (UART2 is safe on ESP32 generally, but ESP32-CAM pins are tight)
// We will use RX=16 (U2RX), TX=14 (HSPI) as these are generally available, but check your board!
HardwareSerial STM32Serial(2);

// 📡 Stream handler
static esp_err_t stream_handler(httpd_req_t *req){
  // Add CORS headers so dashboard can access it
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  
  camera_fb_t * fb = NULL;

  httpd_resp_set_type(req, "multipart/x-mixed-replace; boundary=frame");

  while(true){
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      return ESP_FAIL;
    }

    httpd_resp_send_chunk(req, "--frame\r\n", 9);
    httpd_resp_send_chunk(req, "Content-Type: image/jpeg\r\n\r\n", 28);
    httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
    httpd_resp_send_chunk(req, "\r\n", 2);

    esp_camera_fb_return(fb);
  }
}

// 🎮 Action handler (Receives commands from Dashboard)
static esp_err_t action_handler(httpd_req_t *req){
    // Add CORS headers
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    char buf[100];
    int ret, remaining = req->content_len;

    // Check for "go" parameter in URL (e.g., /action?go=F)
    size_t buf_len = httpd_req_get_url_query_len(req) + 1;
    if (buf_len > 1) {
        if (httpd_req_get_url_query_str(req, buf, buf_len) == ESP_OK) {
            char param[32];
            if (httpd_query_key_value(buf, "go", param, sizeof(param)) == ESP_OK) {
                Serial.print("Dashboard Command: ");
                Serial.println(param);
                
                // Send the command directly to STM32 via UART
                STM32Serial.println(param);
            }
        }
    }
    
    httpd_resp_send(req, "OK", HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

// 🚀 Start server
void startCameraServer(){
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  // We need to support multiple URIs now (one for stream, one for actions)
  config.max_uri_handlers = 4; 

  httpd_uri_t stream_uri = {
    .uri = "/",
    .method = HTTP_GET,
    .handler = stream_handler,
    .user_ctx = NULL
  };

  httpd_uri_t action_uri = {
    .uri = "/action",
    .method = HTTP_GET,
    .handler = action_handler,
    .user_ctx = NULL
  };

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
    httpd_register_uri_handler(stream_httpd, &action_uri);
  }
}

void setup() {
  Serial.begin(115200);   // ⚠️ IMPORTANT → set Serial Monitor to 115200
  
  // Start serial connection to STM32
  // Check your ESP32-CAM schematic for safe UART pins. Pins 14 (TX) and 15 (RX) or 16(RX) can sometimes be used.
  // We'll use 16 and 14 for this example. Connect STM32 TX to ESP32 Pin 16, and STM32 RX to ESP32 Pin 14.
  STM32Serial.begin(115200, SERIAL_8N1, 16, 14); 

  // ✅ Disable brownout reset
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  // 📷 Camera config
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // 📷 Adjust quality if needed
  config.frame_size = FRAMESIZE_VGA;   // try QVGA if slow
  config.jpeg_quality = 12;
  config.fb_count = 2;

  // Init camera
  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("❌ Camera init failed");
    return;
  }

  // 🌐 Connect WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\n✅ WiFi connected");

  // 📡 Show IP
  Serial.print("📷 Stream & API URL: http://");
  Serial.println(WiFi.localIP());

  // 🚀 Start server
  startCameraServer();
}

void loop() {
  // Pass any data received from STM32 back to the PC serial monitor for debugging
  if (STM32Serial.available()) {
    String stmMessage = STM32Serial.readStringUntil('\n');
    Serial.println("STM32 Says: " + stmMessage);
  }
  delay(10);
}
```

---

## 2. Connecting ESP32-CAM to STM32

The updated code uses UART to send the dashboard commands (like `F`, `B`, `L`, `R`, `S`) to the STM32.

1. **Connect Grounds:** Ensure the GND pin of the ESP32-CAM is connected to the GND pin of the STM32.
2. **Connect UART Pins:** 
   * Connect ESP32 **Pin 14 (TX)** to the **STM32 RX pin**.
   * Connect ESP32 **Pin 16 (RX)** to the **STM32 TX pin**.
   *(Note: ESP32-CAM pins are very limited because the camera uses most of them. Pins 14, 15, and 16 are usually the safest to use for extra UART).*

## 3. How it Works with the Dashboard

1. After flashing this code to your ESP32-CAM, open the Serial Monitor (115200 baud).
2. Wait for it to connect to your `iot5` Wi-Fi network and it will print an IP address (e.g., `192.168.1.150`).
3. Open `c:\robot\dashboard\index.html` in your web browser.
4. Enter that exact IP Address into the dashboard and click **Connect**.
5. The live video will start streaming in the dashboard.
6. When you click **Forward**, the dashboard sends a request to `http://<IP>/action?go=F`. The ESP32 receives this, and sends `F` out of Pin 14 directly into your STM32!

---

## 4. Updates to the Code (`robot_main.py` and Dashboard)

Based on the architecture above, the Dashboard now only needs the IP address of the ESP32-CAM. The STM32/ESP32 board running `robot_main.py` no longer connects to Wi-Fi. It simply listens to the ESP32-CAM via UART!

I have already updated the following for you:

1. **Dashboard (`script.js` and `index.html`)**:
   - The dashboard now only asks for one IP address (the Camera IP).
   - When you click a button or use a slider, it sends the command directly to the ESP32-CAM's Action API (e.g. `/action?go=BASE=90`).

2. **Robot Control Board (`robot_main.py`)**:
   - Removed the Wi-Fi and Socket setup sections.
   - Initialized UART on `UART(2)`.
   - The main loop now checks `uart.any()` to receive commands forwarded by the ESP32-CAM instead of checking `skt.accept()`.

### Wiring Reminder

Make sure your ESP32-CAM is connected to the STM32 (or whichever main control board you are using) as follows:
- **ESP32-CAM Pin 14 (TX)** <------> **Main Board UART RX**
- **ESP32-CAM Pin 16 (RX)** <------> **Main Board UART TX**
- **GND** <-----------------------> **GND**

This offloads the heavy Wi-Fi and Camera tasks to the ESP32-CAM, freeing up your main board to focus purely on motor control, servos, and sensors!
