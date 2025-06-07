#include <stdio.h>
#include <periph/adc.h>
#include <periph/gpio.h>
#include <periph/i2c.h>
#include <ztimer.h>
#include <dht.h>

#include "esp_wifi.h"
#include "net/sock/tcp.h"
#include "net/ipv4/addr.h"
// #include "net/sock/dns.h"

#define MAIN_QUEUE_SIZE (8)
static msg_t _main_msg_queue[MAIN_QUEUE_SIZE];

#define light_sensor_gpio ADC_LINE(0)
#define dht22_gpio GPIO_PIN(1, 2)

#define SERVER_PORT 5000
#define BUFFER_SIZE 512
#define SERVER_HOST "nico-behrens.de"

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

void read_dht_value(dht_t *dev, int16_t *temperature, int16_t *humidity) {
    int res = dht_read(dev, temperature, humidity);
    if (res != DHT_OK) {
        printf("DHT read failed: %d\n", res);
    }
}

int32_t read_light_value(void) {
    int32_t value = adc_sample(light_sensor_gpio, ADC_RES_10BIT);
    return value;
}

static void construct_http_request(int16_t temperature, int16_t humidity, char *http_request) {
    // Construct an HTTP POST request that contains the temperature and humidity data
    snprintf(http_request, BUFFER_SIZE,
             "POST / HTTP/1.1\r\n"
             "Host: %s\r\n"
             "Content-Type: application/x-www-form-urlencoded\r\n"
             "Content-Length: %u\r\n"
             "\r\n"
             "temperature=%d&humidity=%d",

             SERVER_HOST,
             strlen("temperature=") + strlen("humidity=") + 20, // 20 for the numbers
             temperature,
             humidity); 
    // printf("Constructed HTTP request:\n%s\n", http_request);
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
    
    ipv4_addr_from_str(&ip, "104.248.255.107");  // or your server IP
    /* if (p_error == NULL) {
        printf("Error: Invalid IP address\n");
        return;
    } */ 

/*     ipv4_addr_t ip_dns;
    error = sock_dns_query("google.com", &ip_dns, AF_INET); // Resolve the server hostname to an IP address
    if (error < 0) {
        printf("Error: DNS query failed (%d)\n", error);
        return;
    } */


    remote.addr.ipv4_u32 = (uint32_t) ip.u32.u32; // Set the IPv4 address in network byte order

    char buffer[BUFFER_SIZE];
    ssize_t res;
 
    /* Connect to the server */
    if ((error = sock_tcp_connect(&sock, &remote, 0, 0)) < 0) {
        printf("Error: Cannot connect to endpoint, %d\n", error);
        return;
    }

    printf("Connected to %s:%d\n", SERVER_HOST, SERVER_PORT);

    /* Send HTTP GET request */
    res = sock_tcp_write(&sock, http_request, strlen(http_request));
    if (res < 0) {
        printf("Error: Cannot send HTTP request (%d)\n", (int)res);
        sock_tcp_disconnect(&sock);
        return;
    }

    printf("Sent HTTP GET request:\n%s\n", http_request);

    /* Receive and print response */
    while ((res = sock_tcp_read(&sock, buffer, BUFFER_SIZE - 1, SOCK_NO_TIMEOUT)) > 0) {
        buffer[res] = '\0'; /* Null-terminate the response */
        printf("%s", buffer);
    }

    if (res < 0) {
        printf("Error: Cannot read response (%d)\n", (int)res);
    }

    /* Disconnect */
    sock_tcp_disconnect(&sock);
    printf("\nConnection closed\n");
}

int main(void) {
    /* Initialize message queue */
    static char http_request[1024];

    ztimer_sleep(ZTIMER_SEC, 1); // Wait for system to stabilize

    msg_init_queue(_main_msg_queue, MAIN_QUEUE_SIZE);

    // i2c_init(I2C_BUS);
    // scan_i2c_devices();
    
    if (adc_init(ADC_LINE(0)) < 0) {
        printf("ADC initialization failed\n");
        return 1;
    }

    dht_params_t dht22_params = {
        .pin = dht22_gpio,
        .type = DHT22,
        .in_mode = GPIO_IN_PU
    };

    dht_t dht22_dev;

    int error = dht_init(&dht22_dev, &dht22_params);
    printf("DHT init error: %d\n", error);

    while (1) {
        // Read the analog value from the A0 pin
        int light = read_light_value();
        if (light < 0) {
            printf("ADC read failed\n");
        } else {
            printf("Light value: %d\n", light);
            // show_number_dec(light, false, 4, 0);
        }

        int16_t humidity, temperature;
        read_dht_value(&dht22_dev, &temperature, &humidity);
        printf("Humidity: %hd%%, Temperature: %hd°C\n", humidity/10, temperature/10);

        construct_http_request(temperature, humidity, http_request);
        send_http_request(http_request);

        ztimer_sleep(ZTIMER_SEC, 3);
    }
    return 0;
}