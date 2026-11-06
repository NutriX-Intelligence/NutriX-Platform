// ============================================================
// FREEnove ESP32-S3 CAMERA + HX711 + OLED
//
// NUTRIX API GATEWAY VERSION
//
// Features:
//   1. Camera web server / live stream
//   2. HX711 load cell
//   3. OLED display
//   4. Push button
//   5. Fresh camera frame on button press
//   6. Multipart POST to NutriX API Gateway
//   7. MAC address sent as User-ID HTTP header
//   8. Weight sent as multipart field
//   9. JPEG sent as multipart field
//  10. JSON response parsing
//  11. Food label + calories + weight + confidence on OLED
//
// ============================================================


#include "esp_camera.h"

#include <WiFi.h>

#include "board_config.h"
#include "camera_pins.h"

#include "HX711.h"

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include <ArduinoJson.h>


// ============================================================
// WIFI
// ============================================================

const char *ssid =
    "JF2GS44";

const char *password =
    "9653434203";


// ============================================================
// NUTRIX API GATEWAY
// ============================================================

const char *SERVER_HOST =
    "192.168.29.232";

const uint16_t SERVER_PORT =
    8000;

const char *SERVER_PATH =
    "/api/v1/ingest/weight-frame";


// ============================================================
// API AUTHENTICATION
// ============================================================

const char *DEVICE_TOKEN =
    "NutriX_ESP32_SECURE_TOKEN";


// ============================================================
// MULTIPART BOUNDARY
// ============================================================

const char *MULTIPART_BOUNDARY =
    "----NutriXESP32Boundary";


// ============================================================
// OLED
// ============================================================

#define OLED_SDA 1
#define OLED_SCL 2

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64


Adafruit_SSD1306 display(
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    &Wire,
    -1
);


// ============================================================
// BUTTON
// ============================================================

#define BUTTON_PIN 3


// ============================================================
// HX711
// ============================================================

const int LOADCELL_DOUT_PIN = 42;
//const int LOADCELL_DOUT_PIN = 16;

//const int LOADCELL_SCK_PIN = 15;
const int LOADCELL_SCK_PIN = 41;

HX711 scale;


// Calibration factor
//const float CALIBRATION_FACTOR = 375.0;
const float CALIBRATION_FACTOR = 330.0;


// ============================================================
// CAMERA SERVER FUNCTIONS
// ============================================================

void cameraInit(void);

void startCameraServer();


// ============================================================
// OLED HELPER
// ============================================================

void showOLED(
    const String &line1,
    const String &line2 = "",
    const String &line3 = "",
    const String &line4 = ""
)
{
    display.clearDisplay();

    display.setTextColor(
        SSD1306_WHITE
    );

    display.setTextSize(1);

    display.setCursor(
        0,
        0
    );

    display.println(
        line1
    );


    if (line2.length() > 0)
    {
        display.setCursor(
            0,
            16
        );

        display.println(
            line2
        );
    }


    if (line3.length() > 0)
    {
        display.setCursor(
            0,
            32
        );

        display.println(
            line3
        );
    }


    if (line4.length() > 0)
    {
        display.setCursor(
            0,
            48
        );

        display.println(
            line4
        );
    }


    display.display();
}


// ============================================================
// SEND CAMERA DATA TO NUTRIX API
// ============================================================
//
// Multipart fields:
//
//     weight
//     image
//
// HTTP headers:
//
//     Device-Token
//     User-ID = ESP32 MAC
//
// ============================================================

void sendCameraData(float weight)
{
    // ========================================================
    // CHECK WIFI
    // ========================================================

    if (
        WiFi.status() != WL_CONNECTED
    )
    {
        Serial.println(
            "ERROR: WiFi not connected"
        );

        showOLED(
            "ERROR",
            "WiFi disconnected"
        );

        return;
    }


    // ========================================================
    // CAPTURE STATUS
    // ========================================================

    Serial.println();

    Serial.println(
        "================================"
    );

    Serial.println(
        "BUTTON CAPTURE"
    );

    Serial.println(
        "Preparing fresh frame..."
    );

    Serial.println(
        "================================"
    );


    showOLED(
        "CAPTURING...",
        "Getting fresh frame"
    );


    // ========================================================
    // DISCARD CURRENT / OLD FRAME
    // ========================================================

    camera_fb_t *oldFrame =
        esp_camera_fb_get();


    if (
        oldFrame != nullptr
    )
    {
        Serial.print(
            "Discarding old frame: "
        );

        Serial.print(
            oldFrame->len
        );

        Serial.println(
            " bytes"
        );

        esp_camera_fb_return(
            oldFrame
        );
    }
    else
    {
        Serial.println(
            "No old frame available"
        );
    }


    // ========================================================
    // GIVE CAMERA TIME TO PRODUCE NEXT FRAME
    // ========================================================

    delay(50);


    // ========================================================
    // CAPTURE FRESH FRAME
    // ========================================================

    camera_fb_t *fb =
        esp_camera_fb_get();


    if (
        fb == nullptr
    )
    {
        Serial.println(
            "ERROR: Fresh camera capture failed"
        );

        showOLED(
            "ERROR",
            "Camera capture",
            "failed"
        );

        return;
    }


    Serial.println(
        "NEW FRAME CAPTURED"
    );


    Serial.print(
        "JPEG size: "
    );

    Serial.print(
        fb->len
    );

    Serial.println(
        " bytes"
    );


    // ========================================================
    // GET MAC ADDRESS
    // ========================================================

    String mac =
        WiFi.macAddress();


    Serial.print(
        "MAC / User-ID: "
    );

    Serial.println(
        mac
    );


    // ========================================================
    // SHOW CAPTURED WEIGHT
    // ========================================================

    display.clearDisplay();

    display.setTextColor(
        SSD1306_WHITE
    );

    display.setTextSize(1);

    display.setCursor(
        0,
        0
    );

    display.println(
        "CAPTURED"
    );

    display.setTextSize(2);

    display.setCursor(
        0,
        20
    );

    display.print(
        weight,
        1
    );

    display.println(
        " g"
    );

    display.display();


    // ========================================================
    // MULTIPART BOUNDARY
    // ========================================================

    String boundary =
        MULTIPART_BOUNDARY;


    // ========================================================
    // WEIGHT FIELD
    // ========================================================

    String partWeight =
        "--" + boundary + "\r\n"
        "Content-Disposition: form-data; "
        "name=\"weight\"\r\n"
        "\r\n"
        + String(weight, 1)
        + "\r\n";


    // ========================================================
    // IMAGE FIELD HEADER
    // ========================================================

    String partImage =
        "--" + boundary + "\r\n"
        "Content-Disposition: form-data; "
        "name=\"image\"; "
        "filename=\"esp32.jpg\"\r\n"
        "Content-Type: image/jpeg\r\n"
        "\r\n";


    // ========================================================
    // MULTIPART END
    // ========================================================

    String partEnd =
        "\r\n--" +
        boundary +
        "--\r\n";


    // ========================================================
    // TOTAL POST SIZE
    // ========================================================

    size_t contentLength =
        partWeight.length()
        + partImage.length()
        + fb->len
        + partEnd.length();


    Serial.print(
        "Total POST size: "
    );

    Serial.print(
        contentLength
    );

    Serial.println(
        " bytes"
    );


    // ========================================================
    // CONNECT TO API GATEWAY
    // ========================================================

    WiFiClient client;


    Serial.print(
        "Connecting to API Gateway: "
    );

    Serial.print(
        SERVER_HOST
    );

    Serial.print(
        ":"
    );

    Serial.println(
        SERVER_PORT
    );


    if (
        !client.connect(
            SERVER_HOST,
            SERVER_PORT
        )
    )
    {
        Serial.println(
            "ERROR: Could not connect to API Gateway"
        );

        esp_camera_fb_return(
            fb
        );

        showOLED(
            "ERROR",
            "API connection",
            "failed"
        );

        return;
    }


    Serial.println(
        "Connected to API Gateway"
    );


    // ========================================================
    // HTTP REQUEST LINE
    // ========================================================

    client.print(
        "POST "
    );

    client.print(
        SERVER_PATH
    );

    client.println(
        " HTTP/1.1"
    );


    // ========================================================
    // HTTP HEADERS
    // ========================================================

    client.print(
        "Host: "
    );

    client.println(
        SERVER_HOST
    );


    client.println(
        "Connection: close"
    );


    // ========================================================
    // DEVICE TOKEN
    // ========================================================

    client.print(
        "Device-Token: "
    );

    client.println(
        DEVICE_TOKEN
    );


    // ========================================================
    // USER-ID = ESP32 MAC ADDRESS
    // ========================================================

    client.print(
        "User-ID: "
    );

    client.println(
        mac
    );


    // ========================================================
    // CONTENT TYPE
    // ========================================================

    client.print(
        "Content-Type: multipart/form-data; boundary="
    );

    client.println(
        boundary
    );


    // ========================================================
    // CONTENT LENGTH
    // ========================================================

    client.print(
        "Content-Length: "
    );

    client.println(
        contentLength
    );


    // End HTTP headers
    client.println();


    // ========================================================
    // SEND WEIGHT FIELD
    // ========================================================

    client.write(
        (const uint8_t *)partWeight.c_str(),
        partWeight.length()
    );


    // ========================================================
    // SEND IMAGE FIELD HEADER
    // ========================================================

    client.write(
        (const uint8_t *)partImage.c_str(),
        partImage.length()
    );


    // ========================================================
    // STREAM JPEG
    // ========================================================

    Serial.println(
        "Streaming JPEG..."
    );


    size_t bytesSent =
        0;


    const size_t CHUNK_SIZE =
        4096;


    while (
        bytesSent < fb->len
    )
    {
        size_t remaining =
            fb->len - bytesSent;


        size_t chunkSize =
            remaining > CHUNK_SIZE
            ? CHUNK_SIZE
            : remaining;


        size_t written =
            client.write(
                fb->buf + bytesSent,
                chunkSize
            );


        if (
            written == 0
        )
        {
            Serial.println(
                "ERROR: JPEG transmission failed"
            );

            break;
        }


        bytesSent +=
            written;
    }


    Serial.print(
        "JPEG bytes sent: "
    );

    Serial.println(
        bytesSent
    );


    // ========================================================
    // SEND MULTIPART END
    // ========================================================

    client.write(
        (const uint8_t *)partEnd.c_str(),
        partEnd.length()
    );


    // ========================================================
    // RETURN CAMERA FRAMEBUFFER
    // ========================================================

    esp_camera_fb_return(
        fb
    );


    // ========================================================
    // WAIT FOR API RESPONSE
    // ========================================================

    Serial.println(
        "Waiting for API response..."
    );


    unsigned long responseStart =
        millis();


    while (
        !client.available()
        &&
        client.connected()
        &&
        millis() - responseStart < 10000
    )
    {
        delay(10);
    }


    if (
        !client.available()
    )
    {
        Serial.println(
            "ERROR: API response timeout"
        );

        client.stop();

        showOLED(
            "ERROR",
            "API timeout"
        );

        return;
    }


    // ========================================================
    // READ HTTP STATUS LINE
    // ========================================================

    String statusLine =
        client.readStringUntil(
            '\n'
        );


    statusLine.trim();


    Serial.print(
        "HTTP Status: "
    );

    Serial.println(
        statusLine
    );


    // ========================================================
    // READ / DISCARD HTTP HEADERS
    // ========================================================

    while (
        client.connected()
        ||
        client.available()
    )
    {
        String line =
            client.readStringUntil(
                '\n'
            );


        line.trim();


        // Empty line = end of HTTP headers

        if (
            line.length() == 0
        )
        {
            break;
        }
    }


    // ========================================================
    // READ RESPONSE BODY
    // ========================================================

    String responseBody =
        "";


    unsigned long bodyStart =
        millis();


    while (
        client.connected()
        ||
        client.available()
    )
    {
        while (
            client.available()
        )
        {
            responseBody +=
                client.readString();

            bodyStart =
                millis();
        }


        // Give the connection a little time to finish

        if (
            millis() - bodyStart > 1000
        )
        {
            break;
        }


        delay(10);
    }


    client.stop();


    // ========================================================
    // PRINT RAW RESPONSE
    // ========================================================

    Serial.println();

    Serial.println(
        "================================"
    );

    Serial.println(
        "RAW API RESPONSE"
    );

    Serial.println(
        "================================"
    );

    Serial.println(
        responseBody
    );

    Serial.println(
        "================================"
    );


    // ========================================================
    // CHECK HTTP 200
    // ========================================================

    if (
        statusLine.indexOf(
            "200"
        ) == -1
    )
    {
        Serial.println(
            "ERROR: API did not return HTTP 200"
        );

        showOLED(
            "API ERROR",
            "HTTP not 200"
        );

        return;
    }


    // ========================================================
    // FIND JSON OBJECT
    // ========================================================
    //
    // The API may return HTTP/body framing around the JSON.
    // We isolate the actual JSON object before parsing it.
    //

    int jsonStart =
        responseBody.indexOf(
            '{'
        );


    int jsonEnd =
        responseBody.lastIndexOf(
            '}'
        );


    if (
        jsonStart < 0
        ||
        jsonEnd < 0
        ||
        jsonEnd <= jsonStart
    )
    {
        Serial.println(
            "ERROR: JSON object not found"
        );

        showOLED(
            "API ERROR",
            "JSON not found"
        );

        return;
    }


    // ========================================================
    // EXTRACT CLEAN JSON
    // ========================================================

    String jsonBody =
        responseBody.substring(
            jsonStart,
            jsonEnd + 1
        );


    jsonBody.trim();


    Serial.println();

    Serial.println(
        "================================"
    );

    Serial.println(
        "CLEAN JSON"
    );

    Serial.println(
        "================================"
    );

    Serial.println(
        jsonBody
    );

    Serial.println(
        "================================"
    );


    // ========================================================
    // PARSE JSON
    // ========================================================

    JsonDocument doc;


    DeserializationError error =
        deserializeJson(
            doc,
            jsonBody
        );


    if (
        error
    )
    {
        Serial.print(
            "JSON parsing failed: "
        );

        Serial.println(
            error.c_str()
        );


        showOLED(
            "API ERROR",
            "JSON parse failed"
        );


        return;
    }


    // ========================================================
    // EXTRACT API VALUES
    // ========================================================

    const char *foodLabel =
        doc["food_label"]
        | "Unknown";


    float calories =
        doc["calories"]
        | 0.0;


    float confidence =
        doc["confidence"]
        | 0.0;


    float backendWeight =
        doc["weight_g"]
        | weight;


    const char *status =
        doc["status"]
        | "unknown";


    const char *sessionId =
        doc["session_id"]
        | "";


    // ========================================================
    // SERIAL RESULT
    // ========================================================

    Serial.println();

    Serial.println(
        "================================"
    );

    Serial.println(
        "NUTRIX RESULT"
    );

    Serial.println(
        "================================"
    );


    Serial.print(
        "Object: "
    );

    Serial.println(
        foodLabel
    );


    Serial.print(
        "Weight: "
    );

    Serial.print(
        backendWeight,
        1
    );

    Serial.println(
        " g"
    );


    Serial.print(
        "Calories: "
    );

    Serial.print(
        calories,
        2
    );

    Serial.println(
        " kcal"
    );


    Serial.print(
        "Confidence: "
    );

    Serial.print(
        confidence,
        1
    );

    Serial.println(
        " %"
    );


    Serial.print(
        "Status: "
    );

    Serial.println(
        status
    );


    Serial.print(
        "Session ID: "
    );

    Serial.println(
        sessionId
    );


    Serial.println(
        "================================"
    );


    // ========================================================
    // OLED RESULT
    // ========================================================

    display.clearDisplay();

    display.setTextColor(
        SSD1306_WHITE
    );


    // --------------------------------------------------------
    // FOOD LABEL
    // --------------------------------------------------------

    display.setTextSize(2);

    display.setCursor(
        0,
        0
    );

    display.println(
        foodLabel
    );


    // --------------------------------------------------------
    // WEIGHT
    // --------------------------------------------------------

    display.setTextSize(1);

    display.setCursor(
        0,
        25
    );

    display.print(
        "Weight: "
    );

    display.print(
        backendWeight,
        1
    );

    display.println(
        " g"
    );


    // --------------------------------------------------------
    // CALORIES
    // --------------------------------------------------------

    display.setCursor(
        0,
        40
    );

    display.print(
        "Calories: "
    );

    display.print(
        calories,
        2
    );

    display.println(
        " kcal"
    );


    // --------------------------------------------------------
    // CONFIDENCE
    // --------------------------------------------------------

    display.setCursor(
        0,
        55
    );

    display.print(
        "Conf: "
    );

    display.print(
        confidence,
        1
    );

    display.print(
        "%"
    );


    display.display();
}


// ============================================================
// SETUP
// ============================================================

void setup()
{
    Serial.begin(
        115200
    );


    Serial.setDebugOutput(
        true
    );


    Serial.println();

    Serial.println(
        "================================"
    );

    Serial.println(
        "ESP32-S3 SYSTEM STARTING"
    );

    Serial.println(
        "================================"
    );


    // ========================================================
    // BUTTON
    // ========================================================

    pinMode(
        BUTTON_PIN,
        INPUT_PULLUP
    );


    Serial.println(
        "Button initialized"
    );


    // ========================================================
    // OLED
    // ========================================================

    Wire.begin(
        OLED_SDA,
        OLED_SCL
    );


    bool oledOK =
        display.begin(
            SSD1306_SWITCHCAPVCC,
            0x3C
        );


    if (
        !oledOK
    )
    {
        Serial.println(
            "WARNING: OLED not found!"
        );
    }
    else
    {
        Serial.println(
            "OLED initialized"
        );


        showOLED(
            "Starting..."
        );
    }

    /*
    // ========================================================
    // HX711
    // ========================================================

    Serial.println(
        "Initializing HX711..."
    );


    scale.begin(
        LOADCELL_DOUT_PIN,
        LOADCELL_SCK_PIN
    );


    scale.set_scale(
        CALIBRATION_FACTOR
    );


    Serial.println(
        "Taring scale..."
    );


    scale.tare();


    Serial.println(
        "HX711 ready!"
    );
    */

    // ============================================================
    // HX711 DIAGNOSTICS
    // ============================================================

    Serial.println();
    Serial.println("========== HX711 DIAGNOSTICS ==========");

    Serial.print("DOUT GPIO: ");
    Serial.println(LOADCELL_DOUT_PIN);

    Serial.print("SCK GPIO: ");
    Serial.println(LOADCELL_SCK_PIN);

    Serial.println("Initializing HX711...");

    scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);

    Serial.println("Checking HX711 readiness...");

    if (scale.wait_ready_timeout(2000)) {

        Serial.println("SUCCESS: HX711 is responding!");

        Serial.println("Setting calibration factor...");
        scale.set_scale(CALIBRATION_FACTOR);

        Serial.println("Taring scale...");
        scale.tare();

        Serial.println("Reading test measurement...");

        float testWeight = scale.get_units(5);

        Serial.print("Test weight: ");
        Serial.print(testWeight, 1);
        Serial.println(" g");

        Serial.println("HX711 diagnostic completed.");

    } else {

        Serial.println("ERROR: HX711 is NOT responding!");
        Serial.println("Check wiring, power, and GPIO connections.");
    }

    Serial.println("=======================================");


    // ========================================================
    // CAMERA
    // ========================================================

    Serial.println(
        "Initializing camera..."
    );


    cameraInit();


    Serial.println(
        "Camera initialized"
    );


    // ========================================================
    // WIFI
    // ========================================================

    Serial.println(
        "Connecting to WiFi..."
    );


    WiFi.begin(
        ssid,
        password
    );


    WiFi.setSleep(
        false
    );


    while (
        WiFi.status() != WL_CONNECTED
    )
    {
        delay(500);

        Serial.print(
            "."
        );
    }


    Serial.println();

    Serial.println(
        "WiFi connected!"
    );


    // ========================================================
    // NETWORK INFORMATION
    // ========================================================

    Serial.print(
        "ESP32 IP: "
    );

    Serial.println(
        WiFi.localIP()
    );


    Serial.print(
        "ESP32 MAC: "
    );

    Serial.println(
        WiFi.macAddress()
    );


    Serial.print(
        "API Gateway: http://"
    );

    Serial.print(
        SERVER_HOST
    );

    Serial.print(
        ":"
    );

    Serial.print(
        SERVER_PORT
    );

    Serial.println(
        SERVER_PATH
    );


    // ========================================================
    // START CAMERA SERVER
    // ========================================================

    Serial.println(
        "Starting camera server..."
    );


    startCameraServer();


    Serial.println(
        "Camera server started"
    );


    // ========================================================
    // READY
    // ========================================================

    if (
        oledOK
    )
    {
        showOLED(
            "SYSTEM READY",
            "Press button"
        );
    }


    Serial.println();

    Serial.println(
        "================================"
    );

    Serial.println(
        "SYSTEM READY"
    );

    Serial.println(
        "Press button"
    );

    Serial.println(
        "================================"
    );
}


// ============================================================
// LOOP
// ============================================================

void loop()
{
    // ========================================================
    // READ CURRENT WEIGHT
    // ========================================================

    float weight =
        scale.get_units(3);


    Serial.print(
        "Weight: "
    );

    Serial.print(
        weight,
        1
    );

    Serial.println(
        " g"
    );


    // ========================================================
    // CONTINUOUS OLED WEIGHT DISPLAY
    // ========================================================

    display.clearDisplay();

    display.setTextColor(
        SSD1306_WHITE
    );


    display.setTextSize(1);

    display.setCursor(
        0,
        0
    );

    display.println(
        "WEIGHT"
    );


    display.setTextSize(2);

    display.setCursor(
        0,
        20
    );

    display.print(
        weight,
        1
    );

    display.println(
        " g"
    );


    display.setTextSize(1);

    display.setCursor(
        0,
        50
    );

    display.println(
        "Press button"
    );


    display.display();


    // ========================================================
    // BUTTON PRESSED
    // ========================================================

    if (
        digitalRead(
            BUTTON_PIN
        ) == LOW
    )
    {
        Serial.println();

        Serial.println(
            "=============================="
        );

        Serial.println(
            "BUTTON PRESSED"
        );

        Serial.println(
            "=============================="
        );


        // ====================================================
        // SHOW CAPTURE STATUS
        // ====================================================

        display.clearDisplay();

        display.setTextColor(
            SSD1306_WHITE
        );

        display.setTextSize(2);

        display.setCursor(
            0,
            10
        );

        display.println(
            "Capturing"
        );

        display.setCursor(
            0,
            35
        );

        display.println(
            "photo..."
        );

        display.display();


        // ====================================================
        // GET FRESH WEIGHT
        // ====================================================

        weight =
            scale.get_units(5);


        Serial.print(
            "Captured weight: "
        );

        Serial.print(
            weight,
            1
        );

        Serial.println(
            " g"
        );


        // ====================================================
        // CAPTURE + UPLOAD
        // ========================================================

        sendCameraData(
            weight
        );


        // ====================================================
        // WAIT FOR BUTTON RELEASE
        // ========================================================

        while (
            digitalRead(
                BUTTON_PIN
            ) == LOW
        )
        {
            delay(10);
        }


        // ====================================================
        // DEBOUNCE
        // ========================================================

        delay(250);
    }


    // ========================================================
    // SMALL DELAY
    // ========================================================

    delay(200);
}


// ============================================================
// CAMERA INITIALIZATION
// ============================================================

void cameraInit(void)
{
    camera_config_t config;


    // ========================================================
    // CAMERA CLOCK
    // ========================================================

    config.ledc_channel =
        LEDC_CHANNEL_0;

    config.ledc_timer =
        LEDC_TIMER_0;


    // ========================================================
    // CAMERA DATA PINS
    // ========================================================

    config.pin_d0 =
        Y2_GPIO_NUM;

    config.pin_d1 =
        Y3_GPIO_NUM;

    config.pin_d2 =
        Y4_GPIO_NUM;

    config.pin_d3 =
        Y5_GPIO_NUM;

    config.pin_d4 =
        Y6_GPIO_NUM;

    config.pin_d5 =
        Y7_GPIO_NUM;

    config.pin_d6 =
        Y8_GPIO_NUM;

    config.pin_d7 =
        Y9_GPIO_NUM;


    // ========================================================
    // CAMERA CONTROL PINS
    // ========================================================

    config.pin_xclk =
        XCLK_GPIO_NUM;

    config.pin_pclk =
        PCLK_GPIO_NUM;

    config.pin_vsync =
        VSYNC_GPIO_NUM;

    config.pin_href =
        HREF_GPIO_NUM;


    config.pin_sccb_sda =
        SIOD_GPIO_NUM;

    config.pin_sccb_scl =
        SIOC_GPIO_NUM;


    config.pin_pwdn =
        PWDN_GPIO_NUM;

    config.pin_reset =
        RESET_GPIO_NUM;


    // ========================================================
    // CAMERA SETTINGS
    // ========================================================

    config.xclk_freq_hz =
        10000000;


    config.frame_size =
        FRAMESIZE_QVGA;


    config.pixel_format =
        PIXFORMAT_JPEG;


    config.grab_mode =
        CAMERA_GRAB_WHEN_EMPTY;


    config.fb_location =
        CAMERA_FB_IN_PSRAM;


    config.jpeg_quality =
        12;


    config.fb_count =
        2;


    // ========================================================
    // PSRAM
    // ========================================================

    Serial.printf(
        "PSRAM: %d bytes\n",
        ESP.getPsramSize()
    );


    Serial.printf(
        "Free PSRAM: %d bytes\n",
        ESP.getFreePsram()
    );


    if (
        psramFound()
    )
    {
        Serial.println(
            "PSRAM found"
        );


        config.jpeg_quality =
            12;


        config.fb_count =
            2;


        config.grab_mode =
            CAMERA_GRAB_WHEN_EMPTY;
    }
    else
    {
        Serial.println(
            "PSRAM not found"
        );


        config.fb_count =
            1;


        config.fb_location =
            CAMERA_FB_IN_DRAM;
    }


    // ========================================================
    // INITIALIZE CAMERA
    // ========================================================

    esp_err_t err =
        esp_camera_init(
            &config
        );


    if (
        err != ESP_OK
    )
    {
        Serial.printf(
            "Camera init failed "
            "with error 0x%x\n",
            err
        );


        return;
    }


    // ========================================================
    // SENSOR SETTINGS
    // ========================================================

    sensor_t *s =
        esp_camera_sensor_get();


    Serial.printf(
        "Camera PID = 0x%04X\n",
        s->id.PID
    );


    s->set_vflip(
        s,
        0
    );


    s->set_brightness(
        s,
        1
    );


    s->set_saturation(
        s,
        0
    );
}