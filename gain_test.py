import hdhr_util as hdhr
import sys
import csv
import time
import numpy
import random
from datetime import datetime
import periodic_and_hopping_GR
import atsc



channelTestList = [10, 43]#[15, 18, 26]
timestoRun=30



def record_to_csv(filename, datalist = []):
    csvfile = open(filename, 'a+')
    writer = csv.writer(csvfile)
    writer.writerow(datalist)
    csvfile.close()
    return True

# initialize data file and csv writer for Test Data Recording
datfilename = "./data_%s.csv" % (datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
datheader = ["Replicate","Signal","Sample Rate","Frequency","Duty Cycle", "Gain","channel","signal", "snq", "seq", "bps", "pps", "time"]
csvfile = open(datfilename, 'w+')
writer=csv.writer(csvfile)
writer.writerow(datheader)
csvfile.close()




deviceID = '1046CFDC'#'1041328E'#hdhr.init_hdhr_1()#'HDHR-1041328E'#
# init values to loop through



tb=periodic_and_hopping_GR.periodic_and_hopping()

def check_interference(seq):
    if seq < 100:
        return False
    else:
        return True

def bts_search(min,max):
    middle = (min + max)/2
    tb.set_gain_slider(middle)
    time.sleep(1.8)
    if (max-min)<=0.5:
        return middle
    status = hdhr.get_status(deviceID)
    print middle,
    if check_interference(seq=status[3]):
        return bts_search(middle, max)
    else:
        return bts_search(min, middle)

def gain_range_ch(channel = 15):
    if channel < 14:
        return -120.0,20.0
    elif channel < 20:
        return -60.0,60.0
    else:
        return -60.0,60.0

def gain_sets_ch(channel = 15):
    if channel < 14:
        return -50.0,70.0
    elif channel < 20:
        return 0.0,60.0
    else:
        return 0.0,60.0

def gain_range_heuristic(oldgain,window):
    return oldgain-window,oldgain+window

def check_search_bond(channeltest, gain, lower, upper):
    gain_min,gain_max = gain_range_ch(channeltest)
    if (gain -lower)<0.5:
        return False, gain_min, gain+5.0
    elif (upper - gain)<0.5:
        return False, gain-5.0, gain_max
    else:
        return True, gain-10, gain+10

# Radio Control Utility
def radio_silent():
    selector = tb.get_selector()
    gain = tb.get_gain_slider()
    tb.set_selector(1) # set periodic signal
    tb.set_duty_cycle(-20) # set duty cycle to 0
    return gain, selector

def radio_hopping():
    tb.set_selector(0)   
    return True

def radio_continuous(gain=-80.0):
    tb.set_gain_slider(gain)
    tb.set_selector(1)
    tb.set_duty_cycle(0)
    return True

def tv_receiver_check(delay=2):
    '''
    Check if TV receiver could decode without interference
    :param delay: seconds of delay between silent and check
    :return:
    '''
    counter = 0
    gain,selector = radio_silent()
    while True:
        time.sleep(delay)
        status = hdhr.get_status(deviceId=deviceID)
        if status[3] == 100: # seq == 100
            break
        elif status[4] == 0: # bps > 0
            counter = counter + 1
            print "TV receiver unable to receive & decode TV signal on this channel, count %d"%(counter)
    tb.set_gain_slider(-80.0)
    tb.set_selector(selector)
    return




samp_rate=5.818182e6 # A sample rate that USB 2.0 could actually support
tb.Start(True)
radio_silent()
tb.set_samp_rate(samp_rate)
num_tones_1MHz = 1400
num_tones_6MHz = tb.get_fft_size()
print "Initialization Complete"
const_window = 55

tb.set_radio_freq(485e6)
# Set to use 6MHz instead of just 1MHz
#num_tones = tb.get_occup_tones()
radio_continuous(10)
#tb.set_occup_tones(num_tones_1MHz)
#tb.set_occup_tones(num_tones_6MHz)

for channeltest in channelTestList:
    freq    = atsc.atsc_freq[channeltest]
    tb.set_gain_slider(-80)
    radio_silent()
    hdhr.tune_to(channeltest,deviceID)
    initial=hdhr.get_status(deviceId=deviceID)

    datalist = [-1,"NC",samp_rate, atsc.atsc_freq[channeltest], 0, "NC", initial[0], initial[1], initial[2], initial[3], initial[4], initial[5], datetime.now().strftime('%Y-%m-%d-%H-%M-%S')]
    # record to data fil5e
    record_to_csv(datfilename,datalist)
    # record SA sensing only

    # Initialize Heuristic Gain and Search Window
    mid,amp = gain_sets_ch(channeltest)
    heuristic_gain = {'Cont_6MHz': mid, 'Cont_1MHz': 6 * [mid], 'Hop_1MHz': mid}
    search_window = {'Cont_6MHz': amp, 'Cont_1MHz': 6 * [amp], 'Hop_1MHz': amp}

    # Run repliactions for each channel
    for idx in range(timestoRun):
        # Step 0: Switch to periodic signal, and set duty cycle to 0
        radio_silent()



        # Step 1: Turn on periodic signal and set duty cycle to 1
        #tb.set_occup_tones(num_tones_1MHz)
        freq_low = freq - 2.5e6 # center frequency of subband 0
        
        #skip 1MHz bands

        # Step 2: Turn on periodic signal with duty cycle 1 and bandwidth 6MHz
        #num_tones_1MHz=tb.get_occup_tones()
        tv_receiver_check()
        tb.set_radio_freq(freq)
        # Set to use 6MHz instead of just 1MHz
        #tb.set_occup_tones(num_tones_6MHz)
        radio_continuous()
        tb.set_selector2(1)
        # Heuristic Searching
        oldgain = heuristic_gain['Cont_6MHz']
        swindow = search_window['Cont_6MHz']
        lower, upper = gain_range_heuristic(oldgain, swindow)
        gain=bts_search(lower, upper)
        trust, lower, upper = check_search_bond(channeltest, gain, lower, upper)
        if not trust:
            gain = bts_search(lower, upper)
        heuristic_gain['Cont_6MHz'] = gain
        search_window['Cont_6MHz'] = const_window
        # End of Searching

        status=hdhr.get_status(deviceId=deviceID)
        datalist = [idx, "Cont_6MHz", samp_rate, freq, 1.0, gain, status[0], status[1], status[2], status[3],
                    status[4], status[5], datetime.now().strftime('%Y-%m-%d-%H-%M-%S')]
        print datalist
        record_to_csv(datfilename, datalist)

       

sys.exit()    
