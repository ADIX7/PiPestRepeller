# The MIT License (MIT)
# Copyright (c) 2022 Mike Teachman
# https://opensource.org/licenses/MIT

# Purpose:  Play a pure audio tone out of a speaker or headphones
#
# - write audio samples_0 containing a pure tone to an I2S amplifier or DAC module
# - tone will play continuously in a loop until
#   a keyboard interrupt is detected or the board is reset
#
# Blocking version
# - the write() method blocks until the entire sample buffer is written to I2S

import os
import sys
import math
import struct
import utime
import micropython_ota
import machine
import requests
import ubinascii
import network
import random
import _thread
import gc
from led import led_init, led_test, time_ms, update_leds
from machine import I2S
from machine import Pin
from time import sleep
from settings import settings
from secrets import secrets

ota_project_name = 'pestrep'
ota_branch = settings['ota_branch']
ota_soft_reset_device=False

ntfy_topic = settings['ntfy_topic']

def make_tone(rate, bits, frequency):
    # create a buffer containing the pure tone samples_0
    samples_0_per_cycle = rate // frequency
    sample_size_in_bytes = bits // 8
    samples_0 = bytearray(int(samples_0_per_cycle * sample_size_in_bytes))
    volume_reduction_factor = 32 # This sound be 32 while developing
    range = pow(2, bits) // 2 // volume_reduction_factor
    
    if bits == 16:
        format = "<h"
    else:  # assume 32 bits
        format = "<l"
    
    for i in range(samples_0_per_cycle):
        sample = range + int((range - 1) * math.cos(2 * math.pi * i / samples_0_per_cycle))
        #sample = int((math.sin(math.pi * 2 * i / samples_0_per_cycle)) * 0.1 * (2 ** 15 - 1))
        struct.pack_into(format, samples_0, i * sample_size_in_bytes, sample)
        
    return samples_0

# Define blinking function for onboard LED to indicate error codes    
def blink_onboard_led(num_blinks):
    led = machine.Pin('LED', machine.Pin.OUT)
    for i in range(num_blinks):
        led.value(1)
        utime.sleep_ms(200)
        led.value(0)
        utime.sleep_ms(200)

def connect_wifi():     
    wlan.active(True)
    # If you need to disable powersaving mode
    # wlan.config(pm = 0xa11140)

    # See the MAC address in the wireless chip OTP
    mac = ubinascii.hexlify(wlan.config('mac'),':').decode()
    print('mac = ' + mac)

    # Other things to query
    # print(wlan.config('channel'))
    # print(wlan.config('essid'))
    # print(wlan.config('txpower'))

    # Load login data from different file for safety reasons
    pw = secrets['pw']

    wlan.connect(ssid, pw)

    # Wait for connection with 10 second timeout
    timeout = 20
    while timeout > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        timeout -= 1
        print('Waiting for connection...')
        blink_onboard_led(2)
        utime.sleep(1)   
    # Handle connection error
    # Error meanings
    # 0  Link Down
    # 1  Link Join
    # 2  Link NoIp
    # 3  Link Up
    # -1 Link Fail
    # -2 Link NoNet
    # -3 Link BadAuth

    wlan_status = wlan.status()
    blink_onboard_led(wlan_status)

    if wlan_status != 3:
        blink_onboard_led(5)
        raise RuntimeError('Wi-Fi connection failed')
    else:
        blink_onboard_led(1)
        print('Connected')
        status = wlan.ifconfig()
        print('ip = ' + status[0])

def disconnect_wifi():
    wlan.disconnect()
    wlan.active(False)
    wlan.deinit()
    print('Disconnected')

def send_notification(title, tags):
    try:
        send_notification_to_server('https://ntfy.sh/' + ntfy_topic, title, tags)
    except:
        print('Error sending notification')
        blink_onboard_led(3)
        send_notification_to_server('https://ntfy.example.com/' + ntfy_topic, title, tags)

def send_notification_to_server(notify_url, title, tags):
    print('Sending notification to ' + notify_url + '...')
    # Send notification
    request = requests.post(notify_url, data="PestRepeller", headers={
        'Title': title, 
        'Priority': '5', 
        'X-Tags': tags
    })
    print(request.content)
    request.close()

# ======= I2S CONFIGURATION =======
SCK_PIN = 16    #BCLK
WS_PIN = 17    #WSEL/LRC
SD_PIN = 18     #DIN
I2S_ID = 0
BUFFER_LENGTH_IN_BYTES = 2000

# ======= AUDIO CONFIGURATION =======
SAMPLE_SIZE_IN_BITS = 16
FORMAT = I2S.MONO  # only MONO supported in this example
# ======= AUDIO CONFIGURATION =======



tones = [
    {
        'frequency_start': int(22_000),
        'frequency_end': int(32_000),
        'sample_rate_multiplier': 2
    }
]
"""
    {
        'frequency_start': int(4_000),
        'frequency_end': int(8_000),
        'sample_rate_multiplier': 4
    } """



print('Starting up...')

led_init()

led_test()

wlan = network.WLAN(network.STA_IF)
ssid = secrets['ssid']

""" try:
    connect_wifi()
    print('Searching for update...')
    micropython_ota.ota_update('https://iot-sw.example.com', ota_project_name, ota_branch)
except:
    print('Error while checking updates') """

# continuously write tone sample buffer to an I2S DAC
print("==========  START PLAYBACK ==========")
last_update_time = time_ms()
last_led_update_time = time_ms()

animation_start_time = time_ms()
animation_duration_ms = 1000
audio_select = 0

sound = 0

def select_next_tone_range(next_tone_id):
    global sound
    global animation_duration_ms
    global animation_start_time
    global animation_direction
    global TONE_START_FREQUENCY_IN_HZ
    global TONE_END_FREQUENCY_IN_HZ
    global sample_rate_multiplier

    animation_start_time = time_ms()
    animation_duration_ms = random.randint(1000, 3000)

    if next_tone_id >= len(tones):
        sound = 0
    else:
        sound = 1
        animation_direction = random.randint(0,1)

        next_tone = tones[next_tone_id]

        tone_start_frequency_in_hz = int(next_tone['frequency_start'])
        tone_end_frequency_in_hz = int(next_tone['frequency_end'])

        tone_diff_half = int(tone_end_frequency_in_hz - tone_start_frequency_in_hz) / 2

        start_frequency = random.randint(tone_start_frequency_in_hz, int(tone_start_frequency_in_hz + tone_diff_half))
        end_frequency = random.randint(int(start_frequency + tone_diff_half), tone_end_frequency_in_hz)

        if end_frequency < start_frequency + tone_diff_half / 3:
            end_frequency = start_frequency + tone_diff_half / 3

        TONE_START_FREQUENCY_IN_HZ = start_frequency
        TONE_END_FREQUENCY_IN_HZ = end_frequency

        sample_rate_multiplier = next_tone['sample_rate_multiplier']

def set_next_tone():
    global audio_out_0
    global samples_0
    global audio_out_1
    global samples_1
    global audio_select
    global animation_start_time
    global animation_duration_ms
    global animation_direction
    global TONE_START_FREQUENCY_IN_HZ
    global TONE_END_FREQUENCY_IN_HZ
    global sample_rate_multiplier

    global I2S_ID
    global SCK_PIN
    global WS_PIN
    global SD_PIN
    global BUFFER_LENGTH_IN_BYTES
    global FORMAT

    delta_frequency = TONE_END_FREQUENCY_IN_HZ - TONE_START_FREQUENCY_IN_HZ
    current_delta_frequency = int(delta_frequency * (time_ms() - animation_start_time) / animation_duration_ms)
    
    if animation_direction == 0:
        current_frequency = TONE_START_FREQUENCY_IN_HZ + current_delta_frequency + random.randint(0, int(delta_frequency / 8))
    else:
        current_frequency = TONE_END_FREQUENCY_IN_HZ - current_delta_frequency - random.randint(0, int(delta_frequency / 8))

    current_sample_rate_in_hz = int(current_frequency * sample_rate_multiplier)

    audio_out = I2S(
        I2S_ID, #I2S_ID,
        sck=Pin(SCK_PIN),
        ws=Pin(WS_PIN),
        sd=Pin(SD_PIN),
        mode=I2S.TX,
        bits=SAMPLE_SIZE_IN_BITS,
        format=FORMAT,
        rate=current_sample_rate_in_hz,
        ibuf=BUFFER_LENGTH_IN_BYTES,
    )
    samples = make_tone(current_sample_rate_in_hz, SAMPLE_SIZE_IN_BITS, current_frequency)

    if audio_select == 1:
        audio_out_0 = audio_out
        samples_0 = samples
        audio_select = 0
    else:
        audio_out_1 = audio_out
        samples_1 = samples
        audio_select = 1


select_next_tone_range(0)

def play_sound():
    global sound
    global audio_select
    global audio_out_0
    global samples_0
    global audio_out_1
    global samples_1
    global run

    while run:
        try:
            if sound > 0:
                if audio_select == 0:
                    audio_out_0.write(samples_0)
                else:
                    audio_out_1.write(samples_1)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print("caught exception in audio thread {} {}".format(type(e).__name__, e))
            sleep(1)
    
    _thread.exit()

select_next_tone_range(0)
set_next_tone()

mode = 0
run = True
second_thread = _thread.start_new_thread(play_sound, ())

while True:
    try:
        current_time = time_ms()

        if current_time - last_led_update_time > 20:
            update_leds()
            last_led_update_time = current_time

        # Check Update
        #try:
        #    if current_time - last_update_time > 36_000_000:
        #        version_changed, remote_version = micropython_ota.check_version('https://iot-sw.example.com', ota_project_name, ota_branch)
        #        if version_changed:
        #            send_notification(title = 'Updating to ' + remote_version, tags = 'new')
        #            if ota_soft_reset_device:
        #                print(f'Found new version {remote_version}, soft-resetting device...')
        #                machine.soft_reset()
        #            else:
        #                print(f'Found new version {remote_version}, hard-resetting device...')
        #                machine.reset()
        #        else:
        #            print('No new version available')
        #        last_update_time = current_time
        #except:
        #    pass

        #print(str(current_time) + ' ' + str(last_update_time))
        if current_time - last_update_time > 500:
            if current_time >= animation_start_time + animation_duration_ms:
                mode = random.randint(0,3)

                if mode == 0:
                    sound = 0
                else: #mode=1 is constant freq, mode=2 is changing freq
                    next_tone_id = random.randint(0, len(tones)-1)
                    select_next_tone_range(next_tone_id)
                    set_next_tone()

                gc.collect()
            elif sound > 0 and mode == 2:
                set_next_tone()
            
            last_update_time = current_time

    except KeyboardInterrupt:
        break
    except Exception as e:
        print("caught exception in main loop {} {}".format(type(e).__name__, e))
        sys.print_exception(e)
        sleep(1)

# cleanup
run = False
audio_out_0.deinit()
audio_out_1.deinit()
print("Done")
