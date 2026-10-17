# =====================================================================
# Smart Irrigation Decision Node - Raspberry Pi Pico W (RP2040)
# TinyML Decision Tree (125 nodes, depth 8) + Rule-based Safeguard Layer
# Telemetry keys EXACTLY match the ThingsBoard dashboard widgets:
#   pot 1 = base name, pot 2 = same name + "_2" suffix
#   crop_id, soil_type, growth_stage, soil_pct,
#   raw_pred, final_decision, mode, temp, humidity
# Pin map: thesis Table 3-9 | Calibration: Table 3-10 | Safeguard: Table 3-7
# Added: MQTT Last Will and Testament (LWT) for offline detection
# =====================================================================

import gc
import time
import json
import network
from machine import ADC, Pin
import dht
from umqtt.simple import MQTTClient
import tree_model

# ---------------------------------------------------------------
# 1) Wi-Fi / ThingsBoard credentials
# ---------------------------------------------------------------
WIFI_SSID = 'Galaxy A54 5G DEC6'
WIFI_PASS = 'a123456a'
TB_HOST   = 'eu.thingsboard.cloud'      # or your own ThingsBoard server
TB_TOKEN  = '0qnkue4ieouq1rl9eooe'        # Device -> Access Token

TELEMETRY_TOPIC = b'v1/devices/me/telemetry'
ATTR_SUB_TOPIC  = b'v1/devices/me/attributes'
ATTR_REQ_TOPIC  = b'v1/devices/me/attributes/request/1'

# ---------------------------------------------------------------
# 2) Pin map (Table 3-9)
# ---------------------------------------------------------------
dht22 = dht.DHT22(Pin(15))
adc_pot1 = ADC(Pin(26))                 # GP26 / ADC0 - Pot 1 (Loam Soil)
adc_pot2 = ADC(Pin(27))                 # GP27 / ADC1 - Pot 2 (Sandy Soil)

led_pot1 = [Pin(16, Pin.OUT), Pin(17, Pin.OUT)]   # Pot 1 LEDs (green)
led_pot2 = [Pin(18, Pin.OUT), Pin(19, Pin.OUT)]   # Pot 2 LEDs (blue)

BZ_ON, BZ_OFF = 0, 1                    # Active-LOW buzzer: 0 = sound, 1 = silent
buzzer = Pin(20, Pin.OUT)
buzzer.value(BZ_OFF)                    # silent at boot (mandatory for active-low)

btn_ack = Pin(21, Pin.IN, Pin.PULL_UP)  # acknowledge button (pressed = 0)


# ---------------------------------------------------------------
# 3) Two-point calibration (Table 3-10): (dry, wet) raw ADC16
# ---------------------------------------------------------------
CAL_P1 = (42698, 19658)  # Pot 1 (Loam)
CAL_P2 = (43194, 19623)  # Pot 2 (Sandy)

# ---------------------------------------------------------------
# 4) Categorical indices - LOCKED to feature_order.json
# ---------------------------------------------------------------
VALID_CROP  = (3, 7)
VALID_SOIL  = (8, 14)
VALID_STAGE = (15, 22)

NAME_TO_IDX = {
    'Carrot': 3, 'Chilli': 4, 'Potato': 5, 'Tomato': 6, 'Wheat': 7,
    'Alluvial': 8, 'Alluvial Soil': 8, 'Black': 9, 'Black Soil': 9,
    'Chalky': 10, 'Chalky Soil': 10, 'Clay': 11, 'Clay Soil': 11,
    'Loam': 12, 'Loam Soil': 12, 'Red': 13, 'Red Soil': 13,
    'Sandy': 14, 'Sandy Soil': 14,
    'Flowering': 15, 'Fruit/Grain': 16, 'Fruit/Grain/Bulb Formation': 16,
    'Germination': 17, 'Harvest': 18, 'Maturation': 19,
    'Pollination': 20, 'Seedling': 21, 'Seedling Stage': 21,
    'Vegetative': 22, 'Vegetative Growth': 22,
    'Vegetative Growth / Root or Tuber Development': 22
}

def parse_to_index(val, valid_range, default_val):
    try:
        if isinstance(val, int):
            target = val
        elif isinstance(val, str):
            val_clean = val.strip()
            if val_clean in NAME_TO_IDX:
                target = NAME_TO_IDX[val_clean]
            elif val_clean.isdigit():
                target = int(val_clean)
            else:
                target = default_val
        else:
            target = default_val
        return target if valid_range[0] <= target <= valid_range[1] else default_val
    except Exception:
        return default_val

# ---------------------------------------------------------------
# 5) Shared attributes - dashboard-native key names
# ---------------------------------------------------------------
DEFAULTS = {
    'thr_emergency':   5,
    'thr_critical':   15,
    'thr_overwet':    85,
    'overwet_cycles':  3,
    'thr_temp_hot':   24,
    'thr_temp_cold':  20,
    'crop_id':      6,
    'soil_type':   12,
    'growth_stage': 22,
    'crop_id_2':      6,
    'soil_type_2':   14,
    'growth_stage_2': 22,
}
ATTRS = dict(DEFAULTS)
ATTR_KEYS = ','.join(DEFAULTS.keys())

POT_KEYS = {
    'pot1': ('crop_id',      'soil_type',    'growth_stage'),
    'pot2': ('crop_id_2',    'soil_type_2',  'growth_stage_2'),
}

# ---------------------------------------------------------------
# 6) System state
# ---------------------------------------------------------------
state = {
    'cycle': 0, 'interventions': 0,
    'reconnects': 0, 'down_ms': 0, 'down_since': 0,
    'silenced': False, 'ow_prev': False, 'ow_until': 0, 'btn_ms': 0,
    'wifi_status': 'offline',
    'env': {'t': 24.0, 'h': 50.0, 'ok': True},
    'pot1': {'raw': 0, 'moi': 0.0, 'rawp': 0, 'fin': 0,
             'mode': 'normal', 'err': False, 'ow': 0},
    'pot2': {'raw': 0, 'moi': 0.0, 'rawp': 0, 'fin': 0,
             'mode': 'normal', 'err': False, 'ow': 0},
}
start_ms = time.ticks_ms()
prev_fin = {'pot1': None, 'pot2': None}
client = None

# ---------------------------------------------------------------
# 7) Network + ThingsBoard connection management
# ---------------------------------------------------------------
def wifi_connect():
    w = network.WLAN(network.STA_IF)
    w.active(True)
    if w.isconnected():
        return w
    # اگر در حال تلاش برای اتصال نیست، فرمان اتصال بده
    if not w.status() == network.STAT_CONNECTING:
        w.connect(WIFI_SSID, WIFI_PASS)
    
    # فقط حداکثر ۱ تا ۲ ثانیه مهلت بده تا حلقه اصلی و ال‌ای‌دی‌ها قفل نشوند
    t0 = time.ticks_ms()
    while not w.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < 1500:
        time.sleep_ms(50)
    return w if w.isconnected() else None

def on_message(topic, msg):
    try:
        d = json.loads(msg)
        if topic.startswith(b'v1/devices/me/attributes/response'):
            d = d.get('shared', d)
        if isinstance(d, dict):
            for k, v in d.items():
                if k in ATTRS:
                    ATTRS[k] = v
            for p in ('pot1', 'pot2'):
                validate_cfg(p)
            print('CFG Updated:', {k: ATTRS[k] for k in ('crop_id', 'soil_type', 'growth_stage', 'crop_id_2', 'soil_type_2', 'growth_stage_2')})
    except Exception as e:
        print('Attr parse error:', e)

def validate_cfg(pot_name):
    ck, sk, gk = POT_KEYS[pot_name]
    ATTRS[ck] = parse_to_index(ATTRS.get(ck), VALID_CROP, DEFAULTS[ck])
    ATTRS[sk] = parse_to_index(ATTRS.get(sk), VALID_SOIL, DEFAULTS[sk])
    ATTRS[gk] = parse_to_index(ATTRS.get(gk), VALID_STAGE, DEFAULTS[gk])
    
def tb_connect():
    global client
    # keepalive را به 30 ثانیه کاهش دادیم تا سرور زودتر متوجه قطعی کلاینت شود
    c = MQTTClient('pico_w', TB_HOST, 1883, TB_TOKEN, '', keepalive=30)
    
    # تنظیم وصیت‌نامه LWT: در صورت قطعی اتصال، خود ThingsBoard این پیام را منتشر می‌کند
    LWT_TOPIC = b'v1/devices/me/attributes'
    lwt_msg = json.dumps({'wifi_status': 'offline', 'device_online': False})
    c.set_last_will(LWT_TOPIC, lwt_msg, qos=1)

    c.set_callback(on_message)
    c.connect()
    c.subscribe(ATTR_SUB_TOPIC)                       # live attribute updates
    c.publish(ATTR_REQ_TOPIC, json.dumps({'clientKeys': ATTR_KEYS}))

    # ارسال وضعیت آنلاین به سرور بلافاصله پس از اتصال
    c.publish(TELEMETRY_TOPIC, json.dumps({'wifi_status': 'online', 'device_online': True}), qos=1)
    state['wifi_status'] = 'online'

    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 3000:
        try:
            c.check_msg()
        except Exception:
            pass
        time.sleep_ms(50)
    for p in ('pot1', 'pot2'):
        validate_cfg(p)
    client = c

def net_maintenance(ms):
    global client
    w = network.WLAN(network.STA_IF)

    # بررسی قطع شدن وای‌فای از سمت ماژول
    if client is not None:
        if not w.isconnected():
            print('NET: Wi-Fi dropped!')
            client = None
            state['wifi_status'] = 'offline'
        else:
            try:
                client.check_msg()        # بررسی دریافت تغییرات ادمین
            except Exception:
                client = None
                state['wifi_status'] = 'offline'
        return

    # مسیر آفلاین: نگهداری مدت‌زمان قطعی و تلاش مجدد برای اتصال
    if state['down_since'] == 0:
        state['down_since'] = ms

    if wifi_connect() is not None:
        try:
            tb_connect()
            state['reconnects'] += 1
            cur_downtime = time.ticks_diff(ms, state['down_since'])
            state['down_ms'] += cur_downtime
            state['down_since'] = 0
            print('NET: reconnected (#%d) after %d ms' % (state['reconnects'], cur_downtime))
            
            # ارسال گزارش قطعی بعد از اتصال موفق
            client.publish(TELEMETRY_TOPIC, json.dumps({
                'wifi_status': 'online',
                'device_online': True,
                'last_downtime_ms': cur_downtime,
                'reconnects': state['reconnects']
            }), qos=1)
        except Exception as e:
            print('TB Reconnect failed:', e)
            client = None

# ---------------------------------------------------------------
# 8) Sensing (64-sample averaging, thesis 3-8)
# ---------------------------------------------------------------
def read_soil(adc, dry, wet):
    total = 0
    for _ in range(64):
        total += adc.read_u16()
        time.sleep_ms(2)
    raw = total // 64
    if raw < 10000 or raw > 60000:
        return raw, 0.0, True
    pct = ((dry - raw) / float(dry - wet)) * 100.0
    pct = max(0.0, min(100.0, pct))
    return raw, round(pct, 1), False

def build_features(moi, temp, hum, ci, si, gi):
    x = [float(moi), float(temp), float(hum)] + [0.0] * 20
    if isinstance(ci, int) and 0 <= ci < 23:
        x[ci] = 1.0
    if isinstance(si, int) and 0 <= si < 23:
        x[si] = 1.0
    if isinstance(gi, int) and 0 <= gi < 23:
        x[gi] = 1.0
    return x

# ---------------------------------------------------------------
# 9) Rule-based Safeguard Layer (Table 3-7)
# ---------------------------------------------------------------
def safeguard(raw_pred, moi, temp, pot):
    fin = raw_pred
    mode = 'normal'
    if moi <= ATTRS['thr_emergency']:
        fin, mode = 2, 'emergency'
    elif moi <= ATTRS['thr_critical'] and temp >= ATTRS['thr_temp_hot']:
        fin, mode = 2, 'rescue'
    elif moi <= ATTRS['thr_critical'] and temp >= ATTRS['thr_temp_cold']:
        fin, mode = 1, 'mild_cold'
    elif moi <= ATTRS['thr_critical']:
        fin, mode = 1, 'mild_cold'

    if moi >= ATTRS['thr_overwet']:
        pot['ow'] += 1
        if pot['ow'] >= ATTRS['overwet_cycles'] and mode == 'normal':
            mode = 'overwet'
    else:
        pot['ow'] = 0

    if fin != raw_pred:
        state['interventions'] += 1
    return fin, mode

# ---------------------------------------------------------------
# 10) Local HMI (Table 3-8)
# ---------------------------------------------------------------
def update_leds(leds, pot, ms):
    if pot['err']:
        c = ms % 1500
        leds[0].value(1 if (c < 100 or 200 <= c < 300) else 0)
        leds[1].value(0)
        return
    f, m = pot['fin'], pot['mode']
    if m == 'overwet':
        leds[0].value(1 if ms % 2000 < 1000 else 0)
        leds[1].value(1)
    elif f == 0:
        leds[0].value(1)
        leds[1].value(0)
    elif f == 1:
        leds[0].value(0)
        leds[1].value(1 if ms % 1000 < 500 else 0)
    elif f == 2:
        leds[0].value(0)
        leds[1].value(1 if ms % 333 < 166 else 0)

def update_buzzer_button(ms):
    global client
    p1, p2 = state['pot1'], state['pot2']
    crit = (p1['fin'] == 2) or (p2['fin'] == 2)
    err  = p1['err'] or p2['err']
    ow   = (p1['mode'] == 'overwet') or (p2['mode'] == 'overwet')

    if btn_ack.value() == 0 and time.ticks_diff(ms, state['btn_ms']) > 200:
        state['btn_ms'] = ms
        if crit:
            state['silenced'] = True
        if client is not None:
            try:
                client.publish(TELEMETRY_TOPIC,
                               json.dumps({'event': 'manual_water', 'ts': ms}),
                               qos=1)
            except Exception:
                client = None

    if not crit:
        state['silenced'] = False

    if ow and not state['ow_prev']:
        state['ow_until'] = ms + 150
    state['ow_prev'] = ow

    if crit and not state['silenced']:
        buzzer.value(BZ_ON if ms % 1000 < 400 else BZ_OFF)
    elif time.ticks_diff(state['ow_until'], ms) > 0:
        buzzer.value(BZ_ON)
    elif err:
        buzzer.value(BZ_ON if ms % 10000 < 150 else BZ_OFF)
    else:
        buzzer.value(BZ_OFF)

# ---------------------------------------------------------------
# 11) Telemetry - dashboard-native key names
# ---------------------------------------------------------------
def publish_telemetry():
    global client
    p1, p2, e = state['pot1'], state['pot2'], state['env']
    try:
        client.publish(TELEMETRY_TOPIC, json.dumps({
            'crop_id':        ATTRS['crop_id'],
            'crop_id_2':      ATTRS['crop_id_2'],
            'soil_type':      ATTRS['soil_type'],
            'soil_type_2':    ATTRS['soil_type_2'],
            'growth_stage':   ATTRS['growth_stage'],
            'growth_stage_2': ATTRS['growth_stage_2'],
            'soil_pct':       p1['moi'],
            'raw_pred':       p1['rawp'],
            'final_decision': p1['fin'],
            'mode':           p1['mode'],
            'soil_pct_2':       p2['moi'],
            'raw_pred_2':       p2['rawp'],
            'final_decision_2': p2['fin'],
            'mode_2':           p2['mode'],
            'temp':     e['t'],
            'humidity': e['h'],
            'interventions': state['interventions'],
            'reconnects':    state['reconnects'],
            'downtime_ms':   state['down_ms'],
            'wifi_status':   state['wifi_status'],
            'device_online': True,
            'cycle':         state['cycle'],
        }), qos=0)
        return True
    except Exception:
        client = None
        state['wifi_status'] = 'offline'
        return False

# ---------------------------------------------------------------
# 12) Scenario console report
# ---------------------------------------------------------------
def report(ms):
    ts = time.ticks_diff(ms, start_ms) // 1000
    e = state['env']
    tag = 'ok' if e['ok'] else 'DHT-ERR'
    net_tag = 'NET:OK' if state['wifi_status'] == 'online' else 'NET:DISCONN'
    for key, label in (('pot1', 'P1'), ('pot2', 'P2')):
        p = state[key]
        print('%6ds %s moi=%5.1f raw=%d final=%d mode=%-9s %s %s' % (
            ts, label, p['moi'], p['rawp'], p['fin'], p['mode'],
            'SENSOR_ERR' if p['err'] else tag, net_tag))
        if prev_fin[key] is not None and prev_fin[key] != p['fin']:
            print('  >>> TRANSITION %s: %d -> %d (mode=%s) @%ds'
                  % (label, prev_fin[key], p['fin'], p['mode'], ts))
        prev_fin[key] = p['fin']

# ---------------------------------------------------------------
# 13) Main loop
# ---------------------------------------------------------------
print('== TinyML Decision Tree + Safeguard Layer + ThingsBoard ==')
gc.collect()
if wifi_connect() is not None:
    try:
        tb_connect()
        state['reconnects'] += 1
        print('TB: connected')
        print('CFG:', ATTRS)
    except Exception:
        client = None
        print('TB: connect failed, will retry in loop')
else:
    print('WiFi: connect failed, will retry in loop')

last_sample = time.ticks_ms()
while True:
    ms = time.ticks_ms()
    net_maintenance(ms)

    if time.ticks_diff(ms, last_sample) >= 2500:
        last_sample = ms
        state['cycle'] += 1

        try:
            dht22.measure()
            state['env'] = {'t': dht22.temperature(),
                            'h': dht22.humidity(), 'ok': True}
        except Exception:
            state['env']['ok'] = False
        t, h = state['env']['t'], state['env']['h']

        for name, adc, cal in (('pot1', adc_pot1, CAL_P1),
                               ('pot2', adc_pot2, CAL_P2)):
            p = state[name]
            p['raw'], p['moi'], p['err'] = read_soil(adc, cal[0], cal[1])
            validate_cfg(name)
            ck, sk, gk = POT_KEYS[name]
            if not p['err']:
                x = build_features(p['moi'], t, h,
                                   ATTRS[ck], ATTRS[sk], ATTRS[gk])
                p['rawp'] = tree_model.predict_tree(x)
                p['fin'], p['mode'] = safeguard(p['rawp'], p['moi'], t, p)

        report(ms)

        if client is not None and state['cycle'] % 2 == 0:
            publish_telemetry()
        gc.collect()

    update_leds(led_pot1, state['pot1'], ms)
    update_leds(led_pot2, state['pot2'], ms)
    update_buzzer_button(ms)
    time.sleep_ms(20)