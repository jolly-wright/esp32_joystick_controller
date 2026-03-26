import gc, time, machine, network, espnow, json, ssd1306
from machine import I2C, Pin, ADC, PWM
#pin setups#

#LED & Buzzer pin
gled = PWM(Pin(12), freq=1000)
gled.duty(0)
buzzer = PWM(Pin(14))
buzzer.duty(0)
#bot selecting switch pin
lock_sw = machine.Pin(15, machine.Pin.IN)
#battery voltage monitor pin
bat = ADC(Pin(33))
bat.atten(ADC.ATTN_11DB)
bat.width(ADC.WIDTH_12BIT)
#left joystick pin setup
ljoystick_sw = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_UP)
ljoystick_x = ADC(Pin(35))
ljoystick_x.atten(ADC.ATTN_11DB)
ljoystick_x.width(ADC.WIDTH_12BIT)
ljoystick_y = ADC(Pin(32))
ljoystick_y.atten(ADC.ATTN_11DB)
ljoystick_y.width(ADC.WIDTH_12BIT)
#right joystick pin setup
rjoystick_sw = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_UP)
rjoystick_x = ADC(Pin(39))
rjoystick_x.atten(ADC.ATTN_11DB)
rjoystick_x.width(ADC.WIDTH_12BIT)
rjoystick_y = ADC(Pin(34))
rjoystick_y.atten(ADC.ATTN_11DB)
rjoystick_y.width(ADC.WIDTH_12BIT)

##NRF24L01+PA+LNA
#MISO - 19
#CE - 4
#CSN - 5
#MOSI - 23
#SCK - 18
time.sleep(0.04)
#OLED SETUP
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 32, i2c)

#WIFI station setup for ESP-NOW
station = network.WLAN(network.STA_IF)
station.active(True)
#ESPNOW COMM
espcom = espnow.ESPNow()
espcom.active(True)
#FUCNTIONS#

#global variables for funcs
joy_select = 0 #shows if joystick movement is upwards or downwards
robo_name = "Unselected" #default name
continuity = 0 #to prevent adding int on each iteration in bot selection
robo_list_iterate = 0 #to iterate thru bot list
robo_list = {"Unselected":b'N/A', "1.RoboSoccer":b'\x80\xf3\xda`(X', "2.MiniRoboSoccer":b'\x80\xf3\xda`(X'}
status = "N/A"
#msg dictionary to send via espnow com
def msg_dic_send(robo_name, mac):
    global espcom
    ljoyx_raw = ljoystick_x.read()
    ljoyy_raw = ljoystick_y.read()
    ljoysw_raw = ljoystick_sw.value()
    rjoyx_raw = rjoystick_x.read()
    rjoyy_raw = rjoystick_y.read()
    rjoysw_raw = rjoystick_sw.value()
    raw_val_list = [ljoyx_raw, ljoyy_raw, rjoyx_raw, rjoyy_raw]
    val_per_list = []
    if ljoysw_raw == 0:
        ljoysw = 1
    else:
        ljoysw = 0
    if rjoysw_raw == 0:
        rjoysw = 1
    else:
        rjoysw = 0
    for i in range(len(raw_val_list)):
        raw_val = raw_val_list[i]
        raw_val_per = int((raw_val/4095)*-200)
        val_per = raw_val_per + 100
        val_per_list.append(val_per)
    val_per = {"ljoyx":val_per_list[0],"ljoyy":val_per_list[1], "rjoyx":val_per_list[2], "rjoyy":val_per_list[3], "ljoysw":ljoysw, "rjoysw":rjoysw}
    #print(mac)
    print(val_per)
    msg = json.dumps(val_per).encode('utf-8')
    try:
        espcom.send(mac, msg)
        return True
    except Exception as e:
        return False
    
#ESP NOW COMM sending func
def esp_now_peer(robo_name):
    global espcom
    if robo_name in robo_list and robo_name != "Unselected":
        mac = robo_list[robo_name]
        espcom.add_peer(mac)
#remote battery voltage checking func
def bat_check():
    bat_adc_total = 0
    for i in range(5):
        bat_adc = bat.read()
        bat_adc_total += bat_adc
    bat_adc_avg = bat_adc_total/5
    bat_vol = ((bat_adc_avg/4095)*9.9)+0.8 #adc error = 0.8
    bat_vol_safe = bat_vol-6
    bat_vol_percentage = (bat_vol_safe/2.4)*100
    if bat_vol_percentage <= 10:
        bat_vol_percentage = 0
        buzzer.duty(412)
        for i in [440, 880, 660, 1212, 1010]:
            buzzer.freq(i)
            time.sleep(0.3)
        buzzer.duty(0)
    if bat_vol_percentage > 100:
        bat_vol_percentage = 100
    return int(bat_vol_percentage)
bat_vol = bat_check() #to check bat right after func definition
#oled text display
def show_oled(selection):
    if selection:
        oled.fill(0)
        oled.text(f"RB:{bat_vol}%", 0, 0)
        oled.text(f"STAT:{status}", 64, 0)
        oled.text("BOT:", 50, 12)
        oled.text(f"{robo_name}", 0, 25)
        oled.show()
    else:
        oled.fill(0)
        oled.text("BOT SELECT:", 16, 2)
        oled.text(f"{robo_name}", 0, 18)
        oled.show()
        gled.duty(0)
#bot selecting function
def bot_select(lock_sw):
    global joy_select, robo_name, continuity, robo_list_iterate, status, bat_vol
    if lock_sw == 0:
        ljoy_y = ljoystick_y.read()
        if ljoy_y >= 4000:
            joy_select = -1
            continuity += 1
        elif ljoy_y <= 100:
            joy_select = 1
            continuity += 1
        else:
            joy_select = joy_select
            continuity = 0
        if joy_select == -1:
            if continuity == 1:
                robo_list_iterate += 1
        elif joy_select == 1:
            if continuity == 1:
                robo_list_iterate -= 1
        else:
            robo_list_iterate = 0
        if robo_list_iterate < 0:
            robo_list_iterate = len(robo_list)-1
        elif robo_list_iterate > len(robo_list)-1:
            robo_list_iterate = 0
        robo_name = list(robo_list.items())[robo_list_iterate][0]
        if continuity > 5:
            continuity = 5 #to prevent over memory usage
        show_oled(False)
        return False
    else:
        return True
#msg receiving for confirm connection aka status checking function
def stat_check(mac):
    try:
        host, confirm = espcom.recv(100)
        if host==mac:
            data = json.loads(confirm)
            print(data)
            if data == 'ok':
                return True
            else:
                return False
        else:
            return False
    except OSError as e:
        return False
#bat and stat check variables
bat_count = 0
stat_error = 0
oled_update = 0
last_status = 'N/A'
#main loop
while True:
    loc_switch = lock_sw.value()
    selection = bot_select(loc_switch)
    if bat_count == 4286: #to check after 5mins instead of wasting 0.1*10=1s on each code iteration
        bat_count = 0
        bat_vol = bat_check()
        gc.collect()
    bat_count += 1
    if selection:
        if (robo_name != "Unselected"):
            try:
                esp_now_peer(robo_name)
            except OSError as e:
                pass
            mac = robo_list[robo_name]
            sender = msg_dic_send(robo_name, mac)
            stat = stat_check(mac)
            if stat and sender:
                status = "OK"
                gled.duty(10)
                stat_error = 0
            else:
                stat_error += 1
            if stat_error > 5:
                status = "N/A"
                gled.duty(0)
        else:
            status = 'N/A'
            gled.duty(0)
    oled_update += 1
    if oled_update > 3:
        show_oled(selection)
        oled_update = 0
    time.sleep(0.07)


