#include <stdio.h>
#include <periph/adc.h>
#include <periph/gpio.h>
#include <periph/i2c.h>
#include <periph/pm.h>
#include <ztimer.h>
#include <dht.h>
#include <math.h>

#include "esp_wifi.h"
#include "net/sock/tcp.h"
#include "net/ipv4/addr.h"
// #include "net/sock/dns.h"

#define MAIN_QUEUE_SIZE (8)
static msg_t _main_msg_queue[MAIN_QUEUE_SIZE];

#define light_sensor_gpio ADC_LINE(0) // this corresponds to GPIO1
#define dht22_gpio GPIO_PIN(0, 41)

#define RESET_INTERVAL_SECONDS (60U*60U)

#define BUFFER_SIZE 1024

typedef struct
{
    int32_t lux;
    int32_t raw;
} light_values_t;

/* void scan_i2c_devices(void) {
    uint8_t address;
    int res;

    printf("Scanning I2C bus...\n");
    for (address = 1; address < 128; address++) {
        i2c_acquire(I2C_BUS);
        char c;
        res = i2c_read_byte(I2C_BUS, address, &c, 0);
        i2c_release(I2C_BUS);

        if (res >= 0) {
            printf("I2C device found at address 0x%02X\n", address);
        }
    }
    printf("Scan complete.\n");
    return;
} */

#define MAXIMUM_TEMPERATURE 60 * 10 // equates to 60 degrees celsius
#define MAXIMUM_HUMIDITY 110 * 10   // equtes to 110% humidity

#define DHT_OK 0
void read_dht_value(dht_t *dev, int16_t *temperature, int16_t *humidity)
{
    uint8_t retries = 3;
    int res;
    do
    {
        res = dht_read(dev, temperature, humidity);

        if (res != DHT_OK)
        {
            LOG_WARNING("DHT read failed: %d\n", res);
        }
        else if (*temperature > MAXIMUM_TEMPERATURE || *humidity > MAXIMUM_HUMIDITY)
        {
            LOG_WARNING("Unusually high DHT values.");
        }
        else if (res == DHT_OK)
        {
            return; // Successfully read the values
        }
    } while (retries-- > 0);
    LOG_ERROR("Failed to read DHT sensor after retries\n");
}

static uint8_t get_digit_count(int32_t value)
{
    uint8_t count = 0;
    if (value < 0)
    {
        count += 1;
        value = -value; // Make it positive for digit count
    }
    if (value == 0)
    {
        return 1; // Special case for zero
    }

    while (value > 0)
    {
        value /= 10;
        count++;
    }
    return count;
}

#define R_FIXED 6000.0       // Fixed resistor: 6kΩ (measured)
#define V_CC 3.3             // Supply voltage
#define ADC_MAX_12BIT 4095.0 // 12-bit ADC maximum value
#define NUM_SAMPLES 30       // Number of samples to average

#define K_CONSTANT 22705.0f
#define Y_CONSTANT 0.57f

void read_light_value(light_values_t *light_values)
{
    // Take multiple samples and average to reduce noise
    uint32_t sum = 0;
    for (int i = 0; i < NUM_SAMPLES; i++)
    {
        sum += adc_sample(light_sensor_gpio, ADC_RES_12BIT);
        ztimer_sleep(ZTIMER_MSEC, 10); // 10ms delay between samples
    }
    int32_t adc_value = sum / NUM_SAMPLES;
    int32_t inverted_adc_value = ((int32_t)ADC_MAX_12BIT) - adc_value; // we invert this here so: low = dark and high = bright

    // Convert ADC to voltage
    float v_measured = (adc_value / ADC_MAX_12BIT) * V_CC;

    // Calculate LDR resistance using voltage divider formula
    // Circuit: VCC -- R_fixed (6kΩ) -- ADC -- R_ldr -- GND
    float r_ldr = R_FIXED * v_measured / (V_CC - v_measured);

    // Convert resistance to lux
    // Calibrated from measurements: R1=2510Ω@14lux, R2=500Ω@750lux
    // LDR behavior: Lower resistance = Brighter (higher lux)
    // Formula: Lux = (K / R)^(1/gamma), where gamma = 0.4, K = 5635
    float lux = pow(K_CONSTANT / r_ldr, 1.0 / Y_CONSTANT); // = pow(5635.0/r_ldr, 2.5)

    printf("ADC: %ld (avg of %d), Voltage: %.2fV, R_ldr: %.0fΩ, Lux: %.0f\n",
           adc_value, NUM_SAMPLES, v_measured, r_ldr, lux);

    light_values->lux = (int32_t)lux;
    light_values->raw = inverted_adc_value;
}

static void construct_http_request(int16_t temperature, int16_t humidity, int32_t lux, int32_t raw_light, char *http_request)
{
    // Construct an HTTP POST request that contains the temperature, humidity, and light data
    // get number of digits in temperature, humidity, and light
    uint8_t temperature_digits = get_digit_count(temperature);
    uint8_t humidity_digits = get_digit_count(humidity);
    uint8_t lux_digits = get_digit_count(lux);
    uint8_t raw_light_digits = get_digit_count(raw_light);

    snprintf(http_request, BUFFER_SIZE,
             "POST /sensor HTTP/1.1\r\n"
             "Host: %s\r\n"
             "Content-Type: application/json\r\n"
             "Content-Length: %u\r\n"
             "Authorization: Bearer %s\r\n"
             "\r\n"
             "{\"temperature\":%d,\"humidity\":%d,\"lux\":%ld,\"raw_light\":%ld}", // this must be in json format

             HOST_NAME,
             strlen("{\"temperature\":") + strlen(",") + strlen("\"humidity\":") + strlen(",") + strlen("\"lux\":") + strlen(",") + strlen("\"raw_light\":}") + temperature_digits + humidity_digits + lux_digits + raw_light_digits,

             API_TOKEN,
             temperature,
             humidity,
             lux,
             raw_light);

    printf("Constructed HTTP request:\n%s\n", http_request);
}

static void send_http_request(char *http_request)
{
    sock_tcp_t sock;
    int error;
    sock_tcp_ep_t remote = {
        .port = SERVER_PORT,
        .family = AF_INET,
    };

    ipv4_addr_t ip;

    ipv4_addr_from_str(&ip, SERVER_IP); // or your server IP

    remote.addr.ipv4_u32 = (uint32_t)ip.u32.u32; // Set the IPv4 address in network byte order

    // static char buffer[BUFFER_SIZE];
    ssize_t res;

    LOG_INFO("Connecting to endpoint...\n");

    /* Connect to the server */
    if ((error = sock_tcp_connect(&sock, &remote, 0, 0)) < 0)
    {
        LOG_ERROR("Cannot connect to endpoint, %d\n", error);
        return;
    }

    LOG_INFO("Connected to %s:%d\n", SERVER_IP, SERVER_PORT);

    /* Send HTTP POST request */
    res = sock_tcp_write(&sock, http_request, strlen(http_request));
    if (res < 0)
    {
        LOG_ERROR("Cannot send HTTP request (%d)\n", (int)res);
        sock_tcp_disconnect(&sock);
        return;
    }

    LOG_INFO("Request sent successfully\n");

    /* Receive and print response - read once with timeout */
    // res = sock_tcp_read(&sock, buffer, BUFFER_SIZE - 1, SOCK_NO_TIMEOUT);
    // printf("read data\n");
    // if (res > 0)
    // {
    //     buffer[res] = '\0'; /* Null-terminate the response */
    //     printf("Response: %s\n", buffer);
    // }
    // else if (res == -ETIMEDOUT)
    // {
    //     LOG_WARNING("Response read timed out\n");
    // }
    // else if (res < 0)
    // {
    //     LOG_ERROR("Cannot read response (%d)\n", (int)res);
    // }
    // else
    // {
    //     LOG_INFO("No response data\n");
    // }

    /* Disconnect */
    sock_tcp_disconnect(&sock);
    LOG_INFO("Connection closed\n\n");
}

int main(void)
{
    /* Initialize message queue */
    static char http_request[BUFFER_SIZE]; // Made static and smaller to avoid stack overflow

    ztimer_sleep(ZTIMER_SEC, 10); // Wait for system to stabilize

    msg_init_queue(_main_msg_queue, MAIN_QUEUE_SIZE);

    // i2c_init(I2C_BUS);
    // scan_i2c_devices();

    if (adc_init(ADC_LINE(0)) < 0)
    {
        LOG_ERROR("ADC initialization failed\n");
        return 1;
    }

    dht_params_t dht22_params = {
        .pin = dht22_gpio,
        .type = DHT22,
        .in_mode = GPIO_IN_PU};

    dht_t dht22_dev;

    int error = dht_init(&dht22_dev, &dht22_params);
    if (error < 0)
    {
        LOG_ERROR("DHT init error: %d\n", error);
        return 1;
    }

    ztimer_now_t start_time = ztimer_now(ZTIMER_SEC);
    LOG_INFO("Entering infinite loop\n");
    while (1)
    {
        ztimer_now_t current_time = ztimer_now(ZTIMER_SEC);

        if ((start_time - current_time) > RESET_INTERVAL_SECONDS) {
            LOG_INFO("Resetting now with %lu seconds passed\n", (start_time - current_time));
            pm_reboot();
        }

        light_values_t light_values;
        // Read the analog value from the A0 pin
        read_light_value(&light_values);
        if (light_values.lux < 0 || light_values.raw < 0)
        {
            LOG_WARNING("ADC read failed");
            light_values.lux = 0;
            light_values.raw = 0;
        }
        else
        {
            LOG_INFO("Lux value: %ld, Raw value: %ld\n", light_values.lux, light_values.raw);
        }

        int16_t humidity, temperature;
        read_dht_value(&dht22_dev, &temperature, &humidity);
        LOG_INFO("Humidity: %hd%%, Temperature: %hd°C\n", humidity / 10, temperature / 10);

        construct_http_request(temperature, humidity, light_values.lux, light_values.raw, http_request);
        send_http_request(http_request);

        ztimer_sleep(ZTIMER_SEC, INTERVAL);
    }
    return 0;
}