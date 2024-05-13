from machine import Pin, ADC, I2C
from ssd1306 import SSD1306_I2C
from fifo import Fifo
from piotimer import Piotimer
import time
import micropython
from time import ticks_ms, sleep_ms

micropython.alloc_emergency_exception_buf(200)

debounce = 250
i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
sw_0 = Pin(9, Pin.IN, Pin.PULL_UP)
oled_width = 128
oled_height = 64
oled = SSD1306_I2C(oled_width, oled_height, i2c)
pixel = 8

class Hr:
    def __init__(self, pin_nr):
        self.adc = ADC(pin_nr)
        self.fifo = Fifo(500)
    
    def handler(self, tid):
        self.fifo.put(self.adc.read_u16())

class Encoder:
    def __init__(self, push):
        self.push = Pin(push, mode=Pin.IN, pull=Pin.PULL_UP)
        self.fifo = Fifo(30, typecode='i')
        self.last_button_press = 0
        self.running = False
        self.last_press_time = 0
        self.debounce_interval = 250
        self.push.irq(handler=self.button_press, trigger=Pin.IRQ_FALLING, hard=True)
    
    def value(self):
        return self.push.value()
    
    def button_press(self, pin):
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_press_time) >= self.debounce_interval:
            self.last_press_time = current_time

def intro():
    text_1 = "PULSE PRO"
    oled.fill(0)
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

def ppi(adc, sample_rate, oled, pixel):
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
    
    tmr = Piotimer(mode=Piotimer.PERIODIC, freq=sample_rate, callback=adc.handler)
    while True:
        while adc.fifo.has_data():
            data = adc.fifo.get()
            #print(f'data: {data} count {count}')
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
                ppi_track += 1# ppi start here
                current_slope = data - prev_value
                #print(f'thresh: {threshold}')
                if current_slope <=0 and prev_slope >0 and data >threshold:
                    if data> max_peak:
                        max_peak = data
                        max_count = count
                        peak_found = True
                if peak_found and data < threshold*0.95:
                    ppi_count.append(max_count)
                    max_count = 0
                    max_peak = 0
                    peak_found = False
                prev_value = data
                prev_slope = current_slope       # ppi ends here
                #print(count)
            if ppi_track % 2500 == 0 and ppi_track != 0 :
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
                screen2 = 'Press the button'
                screen3 = 'to stop'
                oled.text(screen1, (oled_width - (pixel*len(screen1))) // 2, (oled_height - pixel) // 2)
                oled.text(screen2, (oled_width - (pixel*len(screen2))) // 2, ((oled_height - pixel) // 2) + pixel*2)
                oled.text(screen3, (oled_width - (pixel*len(screen3))) // 2, ((oled_height - pixel) // 2) + pixel*3)
                oled.show()
                oled.fill(0)
                
            """
            if encoder.push.value() == 0:
                button_pressed = True
           
            if button_pressed:
                oled.fill(0)
                tmr.deinit()
                return
                
            button_pressed = False"""
            
adc = Hr(26) 
encoder = Encoder(12)

sample_rate = 250

# main program starts here
intro()
time.sleep(2)
instruction()
while True:
    while encoder.value() == 0:
        collect()
        oled.fill(0)
        ppi(adc, sample_rate, oled, pixel)



