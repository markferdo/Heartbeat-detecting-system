from machine import Pin, I2C, ADC
from ssd1306 import SSD1306_I2C
import time
import micropython
from fifo import Fifo
from piotimer import Piotimer
import math
import network
from time import sleep
#from umqtt.simple import MQTTClient
import mip
import ujson

micropython.alloc_emergency_exception_buf(200)

SSID = "KME761_Group_7"
PASSWORD = "Visalmarkrabin"
BROKER_IP = "192.168.7.253"
CLIENT_ID = "pico_hrv_monitor"

class Hr:
    def __init__(self, pin_nr):
        self.adc = ADC(pin_nr)
        self.fifo = Fifo(500)
    
    def handler(self, tid):
        self.fifo.put(self.adc.read_u16())

class Encoder:
    def __init__(self, pin_a, pin_b, pin_sw, debounce_interval):
        self.pin_a = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self.pin_b = Pin(pin_b, Pin.IN, Pin.PULL_UP)
        self.pin_sw = Pin(pin_sw, Pin.IN, Pin.PULL_UP)
        self.debounce_interval = debounce_interval
        self.last_press_time = 0
        self.state = "MENU"
        self.screen = 0
        self.option = 1
        self.pin_b.irq(handler=self.rotation, trigger=Pin.IRQ_FALLING, hard=True)
        self.pin_sw.irq(handler=self.button_press, trigger=Pin.IRQ_FALLING, hard=True)
        
    def rotation(self, pin):
        if self.screen == 0:
            if self.pin_b.value():
                self.option (self.option % 4) + 1
                self.screen.OLED_Menu(self.option)
            else:
                self.option = (self.option - 2)% 4 + 1
                self.screen.OLED_Menu(self.option)
        pass

    def button_press(self, pin):
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_press_time) >= self.debounce_interval:
            self.last_press_time = current_time
            if self.state == "MENU":
                self.state = "INTRO"
            elif self.state == "INTRO":
                self.state = "PPI"
            elif self.state == "PPI":
                self.state = "MENU"

class OLED_Menu:
    def __init__(self, oled, menu_options):
        self.oled = oled
        self.menu_options = menu_options
        self.menu_index = 0

    def update(self):
        self.oled.fill(0)
        y = (oled_height - len(self.menu_options) * 10) // 2
        for i, option_text in enumerate(self.menu_options):
            x = (oled_width - len(option_text) * pixel) // 2
            self.oled.text(option_text, x, y + i * 10)
            if i == self.menu_index:
                self.oled.text(">", x - 10, y + i * 10)
        self.oled.show()

def intro():
    text_1 = "PULSE PRO"
    
    x1 = (oled_width - pixel*len(text_1))//2
    y1 = (oled_height - pixel)//2
    oled.fill(0)
    oled.text(text_1, x1, y1)
    oled.show()
    oled.fill(0)

def instruction():
    oled.fill(0)
    text1 = "HOLD THE SENSOR"
    text2 = "PROPERLY"
    text3 = "PRESS THE BUTTON"
    text4 = "TO START"
    x1 = (oled_width - pixel*len(text1))//2
    x2 = (oled_width - pixel*len(text2))//2
    x3 = (oled_width - pixel*len(text3))//2
    x4 = (oled_width - pixel*len(text4))//2
    oled.text(text1, x1, 4)
    oled.text(text2, x2, 20)
    oled.text(text3, x3, 36)
    oled.text(text4, x4, 52)
    oled.show()

def collect():
    oled.fill(0)
    text1 = "COLLECTING"
    text2 = "....DATA...."
    x1 = (oled_width - pixel*len(text1))//2
    x2 = (oled_width - pixel*len(text2))//2
    oled.text(text1, x1, 27, 1)
    oled.text(text2, x2 , 37, 1)
    oled.show()

def ppi(adc, oled, pixel):
    sample_rate = 250
    sample = []
    ppi_count = []
    tem_ppi_count = []
    count = 0
    ppi_track =0
    prev_value = 0
    prev_slope = 0
    max_peak = 0
    max_count = 0
    peak_found = False
    keep_running = True
    threshold_found = False
    button_pressed = False
    
    tmr = Piotimer(mode=Piotimer.PERIODIC, freq=sample_rate, callback=adc.handler)
    while True:
        while adc.fifo.has_data():
            data = adc.fifo.get()
            sample.append(data)
            if len(sample) % 500 ==0 and len(sample) != 0:
                min_value = min(sample)
                max_value = max(sample)
                threshold = ((min_value + max_value)/2)*1.05
                print(f'data: {data} min: {min_value} max: {max_value} threshold: {threshold} count: {count}')
                threshold_found = True
                sample.clear()
            count = count + 1
            if threshold_found:
                ppi_track += 1
                current_slope = data - prev_value
                if current_slope <=0 and prev_slope >0 and data >threshold:
                    if data> max_peak:
                        max_peak = prev_value
                        max_count = count
                        peak_found = True
                if peak_found and data < threshold*0.95: #3 ppi starts here
                    ppi_count.append(max_count)
                    max_count = 0
                    max_peak = 0
                    peak_found = False
                prev_value = data
                prev_slope = current_slope       # ppi ends here
            if ppi_track % 2500 == 0 and ppi_track != 0:
                length = []
                for i in range(len(ppi_count)-1):
                    samples = ppi_count[i+1] - ppi_count[i]
                    length.append(samples)

                sample_time = 1/250 

                no_of_sample_avg = sum(length)/len(length)
                ppi = no_of_sample_avg*sample_time 

                frequency = 1/ppi
                bpm = 60/(ppi)
                ppi_count.clear()

                print(f'BPM: {bpm}')
                        
                screen1 = f"BPM: {round(bpm)}"
                screen2 = 'PRESS tHE BUTTON'
                screen3 = 'TO STOP'
                oled.text(screen1, (oled_width - (pixel*len(screen1))) // 2, (oled_height - pixel) // 2 - pixel)
                oled.text(screen2, (oled_width - (pixel*len(screen2))) // 2, ((oled_height - pixel) // 2) + pixel*2)
                oled.text(screen3, (oled_width - (pixel*len(screen3))) // 2, ((oled_height - pixel) // 2) + pixel*3+3)
                oled.show()
                oled.fill(0)
            
            if encoder.pin_sw.value() == 0:
                button_pressed = True
           
            if button_pressed:
                oled.fill(0)
                tmr.deinit()
                return
                
            button_pressed = False
            
"""
def ppi_hr(adc, oled, pixel):
    sample_rate = 250

    sample = []
    ppi_count = []
    tem_ppi_count = []
    ppi_for_hr = []
    count = 0
    ppi_track =0

    prev_value = 0
    prev_slope = 0
    max_peak = 0
    max_count = 0
    peak_found = False
    keep_running = True
    threshold_found = False
    
    tmr = Piotimer(mode=Piotimer.PERIODIC, freq=sample_rate, callback=adc.handler)
    
    while count <= 7500:
        while adc.fifo.has_data():
            data = adc.fifo.get()
            sample.append(data)
            if len(sample) == 500:
                min_value = min(sample)
                max_value = max(sample)
                threshold = ((min_value + max_value)/2)*1.05
                print(f'data: {data} min: {min_value} max: {max_value} threshold: {threshold}')
                threshold_found = True
                sample.clear()
            count = count + 1
            if threshold_found:
                ppi_track += 1
                current_slope = data - prev_value
                if current_slope <=0 and prev_slope >0 and data >threshold:
                    if data> max_peak:
                        max_peak = data
                        max_count = count
                        peak_found = True
                if peak_found and data < threshold*0.95: #3 ppi starts here
                    ppi_count.append(max_count)
                    max_count = 0
                    max_peak = 0
                    peak_found = False
                prev_value = data
                prev_slope = current_slope       # ppi ends here
            if count % 7500 == 0 and count != 0:
                length = []
                for i in range(len(ppi_count)-1):
                    samples = ppi_count[i+1] - ppi_count[i]
                    length.append(samples)

                sample_time = 1/250 

                no_of_sample_avg = sum(length)/len(length)
                ppi = no_of_sample_avg*sample_time 

                ppi_for_hr.append(ppi)
                return ppi_for_hr
"""

def calculation(ppi):
    n = len(ppi)
    
    mean_ppi = sum(ppi) / n
    
    hr = 60/mean_ppi
    
    variance = sum((i - mean_ppi) ** 2 for i in ppi) / (n - 1)
    sdnn = math.sqrt(variance)
    
    differences = [ppi[i] - ppi[i-1] for i in range(1, len(ppi))]
    squared_differences = [diff ** 2 for diff in differences]
    mean_squared_diff = sum(squared_differences) / len(squared_differences)
    rmssd = math.sqrt(mean_squared_diff)
    
    
def connect_wlan():
  wlan = network.WLAN(network.STA_IF)
  wlan.active(True)
  wlan.connect(SSID, PASSWORD)

  while not wlan.isconnected():
    print("Connecting... ")
    sleep(1)

  print("Connection successful. Pico IP:", wlan.ifconfig()[0])

def connect_mqtt():
  mqtt_client = MQTTClient(CLIENT_ID, BROKER_IP)
  mqtt_client.connect(clean_session=True)
  return mqtt_client

    

i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
sw_0 = Pin(9, Pin.IN, Pin.PULL_UP)
oled_width = 128
oled_height = 64
oled = SSD1306_I2C(oled_width, oled_height, i2c)
pixel = 8

intro()
time.sleep(2)
menu_options = ["1.MEASURE HR", "2.HRV ANALYSIS", "3.KUBIOS", "4.HISTORY"]

display = OLED_Menu(oled, menu_options)
adc = Hr(26) 
encoder = Encoder(12,11,12,250)
display.update()

while True: 
    if encoder.state == "INTRO":
        instruction()
    elif encoder.state == "PPI":
        collect()
        oled.fill(0)
        ppi(adc, oled, pixel)
    elif encoder.state == "MENU":
        display.update()
    time.sleep(0.1)
