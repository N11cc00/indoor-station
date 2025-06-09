include .env

BOARD ?= esp32s3-devkit
RIOTBASE ?= /home/nico/dev/riot
APPLICATION = sensor-station

LWIP ?= 1
LWIP_UDP ?= 1

### Sensor drivers and misc
USEMODULE += periph_gpio
USEMODULE += periph_adc
USEMODULE += periph_i2c
USEMODULE += ztimer
USEMODULE += ztimer_msec
USEMODULE += ztimer_sec
USEMODULE += dht
USEMODULE += hd44780
USEMODULE += pcf8574


### ESP32 WiFi
USEMODULE += esp_wifi

# USEMODULE += sock_dns
# USEMODULE += auto_init_sock_dns

CFLAGS += -DSOCK_HAS_IPV4=1
CFLAGS += -DCONFIG_AUTO_INIT_SOCK_DNS_SERVER_ADDR=\"1.1.1.1\"

### LWIP stack
USEMODULE += ipv4_addr
USEMODULE += lwip_arp
USEMODULE += lwip_ipv4
USEMODULE += lwip_dhcp_auto
CFLAGS += -DETHARP_SUPPORT_STATIC_ENTRIES=1
USEMODULE += lwip
USEMODULE += lwip_udp
USEMODULE += lwip_tcp

### Socket API
USEMODULE += sock_async_event
USEMODULE += sock_ip
USEMODULE += sock_udp
USEMODULE += sock_tcp

USEMODULE += iolist

CFLAGS += -DDEVELHELP

# for WiFi access
CFLAGS += -DWIFI_SSID=\"${WIFI_SSID}\"
CFLAGS += -DWIFI_PASS=\"${WIFI_PASS}\"
CFLAGS += -DCONFIG_AUTO_INIT_SOCK_DNS_SERVER_ADDR=\"1.1.1.1\"

# for API access to the endpoint
CFLAGS += -DAPI_TOKEN=\"${API_TOKEN}\"

CFLAGS += -DPCF857X_PARAM_ADDR=0x07

include $(RIOTBASE)/Makefile.include