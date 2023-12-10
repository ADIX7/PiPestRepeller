import utime
import random
from machine import Pin

def time_ms() -> int:
    return int(utime.ticks_ms())

""" global led1
global led2
global led3
global led4
global led1_state
global led2_state
global led3_state
global led4_state
global next_on_time_1
global next_on_time_2
global next_on_time_3
global next_on_time_4 """

led1 = Pin(2, Pin.OUT)
led2 = Pin(3, Pin.OUT)
led3 = Pin(4, Pin.OUT)
led4 = Pin(5, Pin.OUT)

current_time = time_ms()
led1_last_time = current_time
led2_last_time = current_time
led3_last_time = current_time
led4_last_time = current_time

led1_state = 0
led2_state = 0
led3_state = 0
led4_state = 0

next_on_time_1 = current_time + 1000
next_on_time_2 = current_time + 1000
next_on_time_3 = current_time + 1000
next_on_time_4 = current_time + 1000

def single_led_test(led):
    led.value(0)
    utime.sleep_ms(400)
    led.value(1)
    utime.sleep_ms(400)

def led_test():
    single_led_test(led1)
    single_led_test(led2)
    single_led_test(led3)
    single_led_test(led4)

def update_led(state, next_on_time, led):
    current_time = time_ms()

    try:
        if state == 0:
            if next_on_time <= current_time:
                state = 1
                next_on_time = current_time + random.randint(100, 400)
                led.value(0)
        else:
            if next_on_time <= current_time:
                state = 0
                led.value(1)
                next_on_time = current_time + random.randint(100, 2000)
    except Exception as e:
        print('Error in update_led: ' + str(e))
        pass

    return state, next_on_time

def update_leds():
    global led1
    global led2
    global led3
    global led4
    global led1_state
    global led2_state
    global led3_state
    global led4_state
    global next_on_time_1
    global next_on_time_2
    global next_on_time_3
    global next_on_time_4

    (led1_state, next_on_time_1) = update_led(led1_state, next_on_time_1, led1)
    (led2_state, next_on_time_2) = update_led(led2_state, next_on_time_2, led2)
    (led3_state, next_on_time_3) = update_led(led3_state, next_on_time_3, led3)
    (led4_state, next_on_time_4) = update_led(led4_state, next_on_time_4, led4)

def led_init():
    global led1
    global led2
    global led3
    global led4

    print('Led init')

    led1.value(1)
    led2.value(1)
    led3.value(1)
    led4.value(1)