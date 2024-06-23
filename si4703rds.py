#!/usr/bin/env python3


HARDWARE='raspi' # raspberry pi
#HARDWARE='none'  # no gpio reset pulse
# later here will be USB for usb-i2c and others

I2C_BUS=1      # 0 for ancient raspberry pi, 1 for newer, other for usb-i2c or other platforms

# for raspi:
PIN_RESET=23   # BCM pin for reset, on common modules mandatory for initializing the chip to I2C
#PIN_IRQ=24     # BCM pin for interrupt, optional
PIN_IRQ=-1     # disable interrupt


RDS_RBDS=0  # 0=RDS, 1=RBDS


#example program for testing the si4703 library
from time import sleep,monotonic
from sys import stdin,stdout,argv,exit
from shutil import get_terminal_size
from math import floor

# RDS_ODA_AID, RDS_GTYPE_desc
from _rdslists import ODAAID_TMC, ODAAID_RTPLUS, RDS_ODAAID_names, RDS_ODA_AID, RDS_GTYPE_desc, RDSPLUS_TAGS, RDS_RBDS_PTY_TYPES, RDS_PI_AREADESC
from _rds_tmc_events import RDS_TMC_EVENTS

from re import split as re_split


# skip loading chip-specific stuff when it is not needed, allow log parsing and help generation on non-raspi machines
if len(argv)<2 or (len(argv)>1 and argv[1] not in ['-','-h','-hi','-cn']):
  try:
    from _libsi4703 import si4703Radio
  except Exception as e:
    s=str(e)
    print('ERROR: failed line: from _libsi4703 import si4703Radio')
    print('ERROR:',e)
    if 'RPi' in s: print('ERROR: Not running on raspberry pi? Or try "pip install RPi"')
    if 'smbus' in s: print('ERROR: try "pip install smbus"')
    exit(1)




#INITFREQ=1050
ONCRASH_OFF=False # switch off radio on program crash?

# filtering of scrolling groups, = means "only"
RDS_FILTERS=[ [], ['0A','2A'], ['=2A'],['=3A'],['=8A'] ]




# scan limits
FREQ_FROM=875        # STATION:  87.5  8    [________]  499
FREQ_TO=1080         # STATION: 108.0  2    [________]  499

Si4703_I2C_ADDR=0x10 # 0x10 by default


##############
##
##  radio init
##
##############

def getradio():
    if HARDWARE=='raspi': return si4703Radio(addr=Si4703_I2C_ADDR, rstpin=PIN_RESET, irqpin=PIN_IRQ, bus=I2C_BUS, hw=HARDWARE)
    if HARDWARE=='none':  return si4703Radio(addr=Si4703_I2C_ADDR, rstpin=-1,        irqpin=-1,      bus=I2C_BUS, hw=HARDWARE)
    print('ERROR: unknown hardware:',HARDWARE)
    raise(BaseException('unknown hardware definition'))



###############################################
##
##  nonblocking stdin read for keypress control
##
###############################################

## https://ballingt.com/nonblocking-stdin-in-python-3/
from fcntl import fcntl,F_GETFL,F_SETFL
from os import O_NONBLOCK
from tty import setcbreak
from termios import tcgetattr,tcsetattr,TCSANOW

class raw(object):
    def __init__(self, stream):
        self.stream = stream
        self.fd = self.stream.fileno()
    def __enter__(self):
        self.original_stty = tcgetattr(self.stream)
        setcbreak(self.stream)
    def __exit__(self, type, value, traceback):
        tcsetattr(self.stream, TCSANOW, self.original_stty)

class nonblocking(object):
    def __init__(self, stream):
        self.stream = stream
        self.fd = self.stream.fileno()
    def __enter__(self):
        self.orig_fl = fcntl(self.fd, F_GETFL)
        fcntl(self.fd, F_SETFL, self.orig_fl | O_NONBLOCK)
    def __exit__(self, *args):
        fcntl(self.fd, F_SETFL, self.orig_fl)



###########################
##
##  bit array manipulations
##
###########################

# get value of val, bit b
def getbit(val,b):
  mask=(1<<b)
  if mask & val: return 1
  return 0

# get value of n bits in at most 16bit val, starting on bit b
def getbits(val,b,n):
  mask=(0xFFFF>>(16-n))<<b
  return (val & mask)>>b

# get value of n bits in at most 48bit val, starting on bit b
def getbits_long(val,b,n):
  mask=(0xFFFFFFFFFFFF>>(48-n))<<b
  return (val & mask)>>b

# get all 37 bits in one number, for packed values
def rds_to_raw(rds):
    return ((rds[1]&0x1f)<<32)+(rds[2]<<16)+(rds[3])



############################
##
##  natural sort
##
############################

# from https://stackoverflow.com/questions/4836710/is-there-a-built-in-function-for-string-natural-sort
def natsort(a):
  natsort = lambda s: [' ' if t=='-' else int(t) if t.isdigit() else t.lower() for t in re_split('(\d+)', s.replace('-','0'))]
  return sorted(a, key=natsort)



############################
##
##  console output functions
##
############################

# print registers
def printreg(radio):
  print()
  print()
  radio.si4703ReadRegisters()
  radio.si4703printreg(hdr=True)

# print value, immediately flush, no newline
def p(s):
    print(s,end='',flush=True)

# get hex string from integer
def hexstr(i,l=4):
    return f'{i:04x}'[4-l:]


def ints2str(i1,i2):
    b=bytes([i1>>8, i1&0xff, i2>>8, i2&0xff])
    #try: return b.decode('utf-8')
    #except: return '????'
    try: return '['+b.decode('utf-8')+']'
    except: return str(b)

def int2str(i1):
    b=bytes([i1>>8, i1&0xff])
    #try: return b.decode('utf-8')
    #except: return '????'
    try: return '['+b.decode('utf-8')+']'
    except: return str(b)

# get formatted packet payload, 37bit, XX:XXXX:XXXX
def hexpayload(rds):
    return hexstr(rds[1]&0x1F,l=2)+':'+hexstr(rds[2])+':'+hexstr(rds[3])


# format frequency
def fmtfreq(i,pad='0'):
    s=(pad*4+str(i))[-4:]
    return s[:3]+'.'+s[3:]

# print line prefix with channel and RSSI
def getchanrssi(chan,radio,spacer=''):
    rssi=radio.si4703getRssi()
    return fmtfreq(chan,pad=' ')+spacer+('    '+str(rssi))[-3:]+'  '

def printchanrssi(chan,radio):
    p(getchanrssi(chan,radio))


# 105.0  R-VLTAVA   0a, 2a, 14a, 14b
#                   GTYPE=14B:EON_B        10:232d:232f
# 102.5  RADIO F1   0a, 1a, 2a, 4a   # GTYPE=4A:clock         01:d6db:2c02    at nov21,1948
#  99.7  Bonton     0a, 1a?, 2a, 4a?   WEAK
#  98.7  CLASSIC    0a, 2a, (14a - rare?)
#  96.6   IMPULS    0a, 2a
#  95.7   SIGNAL    0a, 2a
#  95.3    BEAT     0a, 2a, 10a(always spaces)
#  94.6  R-ZURNAL   0a, 1a, 2a, 3a, 4a, 8a (JSDI)
#                   GTYPE=3A:openDataAppId 10:0647:cd46 grp=8A msg=0647 appId=cd46(RDS-TMC ALERT-C)
#                   GTYPE=8A:TMC           05:c9ed:28b0 usermsg
#                   GTYPE=1A:progItemNoSlo 02:0000:0000
#                   GTYPE=8A:TMC           05:4964:6000 usermsg
#                   GTYPE=8A:TMC           0f:c2e7:64e3 usermsg 1grp dur=7 diversion=1 dir=1 scale=0 event=74302e7 loc=c2e7 multigrp firstblk=1
#                   GTYPE=4A:clock         01:d6de:1780    # nov23,0130
#  93.7  CITY 937   0a, 2a, 3a, 11a
#                   GTYPE=3A:openDataAppId 16:0000:4bd7 grp=11A msg=0000 appId=4bd7
#                   GTYPE=11A              18:2b94:2013
#                   GTYPE=3A:openDataAppId 16:0000:4bd7 grp=11A msg=0000 appId=4bd7
#                   GTYPE=11A              18:2e1c:2018
# (92.6) CROplus    0a, 1a, 2a, 3a, 8a? (PRG-only)   4a? 01:d6d2:5e40
#                   GTYPE=3A:openDataAppId 10:4080:cd46 grp=8A msg=4080 appId=cd46
#                   GTYPE=8A:TMC           06:0000:0000 usermsg
#                   GTYPE=8A:TMC           07:cabd:11f7 usermsg
#                   GTYPE=8A:TMC           07:cabd:a1a3 usermsg
#                   GTYPE=8A:TMC           07:51a2:ac00 usermsg
#  903   EXPRESFM   0a, 2a, 4a?
#  895   COUNTRY    0a, 2a, 10a (all spaces)



# http://www.interactive-radio-system.com/docs/EN50067_RDS_Standard.pdf
# https://www.ni.com/docs/en-US/bundle/rfmx-waveform-creator/page/rds-common-parameters.html
# https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/dl_common_library/dl_manuals/gb_1/s/digital_standards_for_signal_generators/RS_SigGen_FM_Stereo-RDS_OperatingManual_en_11.pdf

# http://www.g.laroche.free.fr/english/rds/groupes/listeGroupesRDS.htm

# 0A: basic tuning
# xtype: TA MS DI c1 c0    TA=traffic-announce,1=traffic; MS=music/speech, DI[c]=decoder info, c1/c0=subaddress
#    DI[0]=mono/stereo,1=stereo
#    DI[1]=head,1=artificial head
#    DI[2]=compress,1=compressed
#    DI[3]=PTY,0=static,1=dynamic
# grp3=AF, alt-freq; AF1/AF0, 8bit numbers; 0=unused, 1..204=87.5+n/10 MHz, 
# grp4=PS, service name - double chars, addressed by c1:c0



"""
monitoring RDS...
1050  232d:e0fd:0800:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '1d', 'GTYPE': '14A:EON         '} TPon=1 var=13 DATA=0800 PIon=232f
1050  232d:e0f0:2020:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '10', 'GTYPE': '14A:EON         '} TPon=1 var=0 DATA=b'  ' PIon=232f
1050  232d:e0f1:4352:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '11', 'GTYPE': '14A:EON         '} TPon=1 var=1 DATA=b'CR' PIon=232f
1050  232d:e0f2:2031:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '12', 'GTYPE': '14A:EON         '} TPon=1 var=2 DATA=b' 1' PIon=232f
1050  232d:e0f3:2020:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '13', 'GTYPE': '14A:EON         '} TPon=1 var=3 DATA=b'  ' PIon=232f
1050  232d:e0f4:e616:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'\xe6\x16' PIon=232f
1050  232d:e0f4:7522:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'u"' PIon=232f
1050  232d:e0f4:e616:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'\xe6\x16' PIon=232f
1050  232d:e0f4:7522:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'u"' PIon=232f
1050  232d:e0f4:38cd:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'8\xcd' PIon=232f
1050  232d:e0fd:0800:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '1d', 'GTYPE': '14A:EON         '} TPon=1 var=13 DATA=0800 PIon=232f
1050  232d:e0f0:2020:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '10', 'GTYPE': '14A:EON         '} TPon=1 var=0 DATA=b'  ' PIon=232f
1050  232d:e0f1:4352:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '11', 'GTYPE': '14A:EON         '} TPon=1 var=1 DATA=b'CR' PIon=232f
1050  232d:e0f2:2031:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '12', 'GTYPE': '14A:EON         '} TPon=1 var=2 DATA=b' 1' PIon=232f
1050  232d:e0f4:e616:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'\xe6\x16' PIon=232f
1050  232d:e0f4:7522:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'u"' PIon=232f
1050  232d:e0f4:e616:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'\xe6\x16' PIon=232f
1050  232d:40e1:d6db:16c0 {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '01', 'GTYPE': '4A:clock        '} 01:d6db:16c0
1050  232d:e0f4:5447:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'TG' PIon=232f
1050  232d:e0f4:7522:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'u"' PIon=232f
1050  232d:e0f4:38cd:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'8\xcd' PIon=232f
1050  232d:e0fd:0800:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '1d', 'GTYPE': '14A:EON         '} TPon=1 var=13 DATA=0800 PIon=232f
1050  232d:e0f0:2020:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '10', 'GTYPE': '14A:EON         '} TPon=1 var=0 DATA=b'  ' PIon=232f
1050  232d:e0f1:4352:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '11', 'GTYPE': '14A:EON         '} TPon=1 var=1 DATA=b'CR' PIon=232f
1050  232d:e0f3:2020:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '13', 'GTYPE': '14A:EON         '} TPon=1 var=3 DATA=b'  ' PIon=232f
1050  232d:e0f4:5447:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'TG' PIon=232f
1050  232d:e0f4:7522:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'u"' PIon=232f
1050  232d:e0f4:38cd:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'8\xcd' PIon=232f
1050  232d:e0f4:e616:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'\xe6\x16' PIon=232f
1050  232d:e0f4:5447:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'TG' PIon=232f
1050  232d:e0f4:7522:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'u"' PIon=232f
1050  232d:e0fd:0800:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '1d', 'GTYPE': '14A:EON         '} TPon=1 var=13 DATA=0800 PIon=232f
1050  232d:e0f1:4352:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '11', 'GTYPE': '14A:EON         '} TPon=1 var=1 DATA=b'CR' PIon=232f
1050  232d:e0f3:2020:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '13', 'GTYPE': '14A:EON         '} TPon=1 var=3 DATA=b'  ' PIon=232f
1050  232d:e0f4:e616:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'\xe6\x16' PIon=232f
1050  232d:e0f4:5447:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'TG' PIon=232f
1050  232d:e0f4:7522:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'u"' PIon=232f
1050  232d:e0f4:38cd:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'8\xcd' PIon=232f
1050  232d:e0f4:e616:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'\xe6\x16' PIon=232f
1050  232d:e0f4:7522:232f {'PIC': '232d', 'B0': 0, 'TP': 0, 'PTY': 7, 'VARY': '14', 'GTYPE': '14A:EON         '} TPon=1 var=4 DATA=b'u"' PIon=232f
done

RT+:
 93.7 12  0000  2032:3556:0000:4bd7  PIC=2032 TP=1 PTY=10 VARY=16  GTYPE=3A:openDataAppId 16:0000:4bd7 grp=11A msg=0000 appId=4bd7(RT+)
 93.7 13  0000  2032:b548:299c:200f  PIC=2032 TP=1 PTY=10 VARY=08  GTYPE=11A:oda-freeform 08:299c:200f
 93.7 12  0000  2032:3556:0000:4bd7  PIC=2032 TP=1 PTY=10 VARY=16  GTYPE=3A:openDataAppId 16:0000:4bd7 grp=11A msg=0000 appId=4bd7(RT+)
 93.7 12  0000  2032:b548:299c:200f  PIC=2032 TP=1 PTY=10 VARY=08  GTYPE=11A:oda-freeform 08:299c:200f
 93.7 12  0000  2032:3556:0000:4bd7  PIC=2032 TP=1 PTY=10 VARY=16  GTYPE=3A:openDataAppId 16:0000:4bd7 grp=11A msg=0000 appId=4bd7(RT+)
 93.7 13  "CITY 937" R  2A 0234b  "ENRIQUE IGLESIAS - Can You Hear Me                              " <filtered:0A,2A>


"""

########################
##
##  RDS helper functions
##
########################

# RDS string array
rds_mem={}            # string arrays for groups
rds_stat={}           # statistics, {'0A':20,'2A':21,...}
rds_qgrps=set()       # quickview set of groups, ('0','2','8','8^',...)
rds_qgrpscnt={}       # quickview count of groups, {'2':12,'8^':1,...) - duplicated stats, for filtering of status line groups show
rds_odagrps={}        # ODA-assigned groups, {'8A':'TMC',...}
rds_odagrpscnt={}     # ODA-assigned group count {'8A':34}
rds_freq={}           # frequencies array
rds_pty=-1            # PTY
rds_pic=-1            # PIC

def rds_stat_reset():
  global rds_stat,rds_qgrps,rds_qgrpscnt,rds_odagrps,rds_odagrpscnt,rds_freq,rds_pty,rds_pic
  rds_stat={'--':0}
  rds_qgrps=set()
  rds_qgrpscnt={}
  rds_odagrps={}
  rds_odagrpscnt={}
  rds_freq={'count':0} # frequencies array
  rds_pty=-1            # PTY
  rds_pic=-1            # PIC

def rds_stat_add(name,grp,b0):
  if name in rds_stat: rds_stat[name]+=1
  else: rds_stat[name]=1
  rds_add_quickqgroups(grp,b0)


# quickgroups list add
def rds_add_quickqgroups(grp,b0):
  if grp<0: return
  if b0:
    if grp<10: c=f'{grp:x}^'
    else: c=f'{grp:X}'
  else: c=f'{grp:x}'
  rds_qgrps.add(c)
  if c in rds_qgrpscnt: rds_qgrpscnt[c]+=1
  else: rds_qgrpscnt[c]=1

# quickgroups list
def rds_get_quickgroups():
  #return ''.join(sorted(rds_qgrps))  # fast and dumb
  tot=sum(rds_qgrpscnt.values())
  if tot==0: return ''
  s=''
  for x in sorted(rds_qgrps):
    #s+=x
    if rds_qgrpscnt[x]/tot > 0.03: s+=x
  return s



# init RDS strings
def rds_initstr(initchar=b'_'):
  global rds_mem
  rds_stat_reset()
  rds_mem['0A'] =bytearray(initchar*8)
  rds_mem['DI']=bytearray(initchar*4)
  rds_mem['2']  =bytearray(initchar*64)
  rds_mem['PTYN'] =bytearray(initchar*8)
  rds_mem['TMCID'] =bytearray(initchar*8)
  rds_mem['clock']='?'
  rds_tmclist_reset()

# set ODAAID for group, from 3A
def rds_setodagrp(grp,val):
  if grp in rds_odagrpscnt: rds_odagrpscnt[grp]+=1
  else: rds_odagrpscnt[grp]=1
  rds_odagrps[grp]=val

# get ODAAID for group
def rds_getodagrp(g,threshold=0.02):
  #threshold=0.05 # at least 5%
  if g in rds_odagrps and g in rds_odagrpscnt:
    # make sure we do not get confused by noise-induced false data
    if rds_odagrpscnt[g]/sum(rds_odagrpscnt.values())>=threshold: return rds_odagrps[g]
  return ''

# get desc for group's ODA assignment
def rds_getodagrpname(g,threshold=0.05):
  gn=rds_getodagrp(g,threshold=threshold);
  if gn=='': return ''
  s=f'0x{gn:04X}'
  if gn in RDS_ODAAID_names: s+='('+RDS_ODAAID_names[gn]+')'
  #if gn==ODAAID_TMC: s+='(TMC)'
  #elif gn==ODAAID_RTPLUS: s+='(RT+)'
  return s



# set character char in RDS string [name] at pos
def rds_setstrraw(name,char,pos):
  if int(char)<0x20: char=0x40
  try: rds_mem[name][pos]=char
  except Exception as e: print('EXCEPT:',e,'name:',name,'len:',len(rds_mem[name]),'pos:',pos)

# print memory string
def rds_getmem(name,quot='"'):
  s=rds_mem[name]
  if isinstance(s,str): return s.replace('\r','\\r')
  try: return quot+s.decode('utf-8').replace('\r','\\r')+quot
  except: return str(rds_mem[name]).replace('bytearray','')

def rds_printmem(name):
  p(rds_getmem(name))

# insert two chars encoded as 16bit integer into string, print the string
def rds_setstr(name,val,pos,out=True):
  rds_setstrraw(name,val>>8  ,pos*2)
  rds_setstrraw(name,val&0xff,pos*2+1)
  if out: rds_printmem(name)

# insert four chars encoded as two 16bit integers into string, print the string
def rds_setstr2(name,val1,val2,pos,out=True):
  rds_setstrraw(name,val1>>8  ,pos*4)
  rds_setstrraw(name,val1&0xff,pos*4+1)
  rds_setstrraw(name,val2>>8  ,pos*4+2)
  rds_setstrraw(name,val2&0xff,pos*4+3)
  if out: rds_printmem(name)

def rds_setstrstr(name,val):
  rds_mem[name]=val




# get RDS group string from group ID and A/B bit
def getrdsgtype(g,b0):
  return str(g)+['A','B'][b0]



def rdslist_get_ODA_AID_name(aid):
  if aid in RDS_ODA_AID: return '('+RDS_ODA_AID[aid]+')'
  return ''

def rdslist_get_grpdesc(grpname):
    # https://www.2wcom.com/fileadmin/redaktion/dokumente/Company/RDS_Basics.pdf
    if grpname in RDS_GTYPE_desc: return grpname+':'+RDS_GTYPE_desc[grpname]
    return grpname
    #if s=='8A': return grpname+':TMC'
    #return grpname



# get alternate frequency from byte to string
def rds_byte2freq(b):
    if b==0: return '[unused]'
    if b<206: return fmtfreq(875+b)
    if b==206: return '[fill]'
    if b==224: return '[noAF]'
    if b>224 and b<250: return '[follow:'+str(b-224)+']'
    if b==250: return '[follow:1LFMF]'
    return '[unassigned]'



def rds_freq_add(freq,grp='',isfm=True):
  if grp in rds_freq and freq in rds_freq[grp]: rds_freq[grp][freq]['cnt']+=1
  else:
    if grp not in rds_freq: rds_freq[grp]={}
    rds_freq[grp][freq]={'cnt':1,'freq':str(freq),'from':grp}

#def rds_freq_add(freq,from='',isfm=True):
def rds_byte2freq_add(b,grp='',isfm=True): # returns True if next freq is low-freq
    if b==0: return False
    if b<206:
      if isfm: rds_freq_add(fmtfreq(875+b,pad=' ').strip(),grp,True);return False
      else: rds_freq_add(str(b)+' raw khz',grp,True);return False
    if b==206: return False
    if b==224: return False
    if b>224 and b<250: rds_freq['count']=b-224;return False
    if b==250: return True
    return False




# https://gist.github.com/jiffyclub/1294443
#     Algorithm from 'Practical Astronomy with your Calculator or Spreadsheet',
#         4th ed., Duffet-Smith and Zwart, 2011.
# get julian day date to year-month-day, for group 4A, clock
def julianday_to_date(jd,modified=True): # param: float julian_day
     import math
     jd = jd + 0.5
     if modified: jd=jd+2400000.5
     F, I = math.modf(jd)
     I = int(I)
     A = math.trunc((I - 1867216.25)/36524.25)
     if I > 2299160: B = I + 1 + A - math.trunc(A / 4.)
     else: B = I
     C = B + 1524
     D = math.trunc((C - 122.1) / 365.25)
     E = math.trunc(365.25 * D)
     G = math.trunc((C - E) / 30.6001)
     day = C - E + F - math.trunc(30.6001 * G)
     if G < 13.5: month = G - 1
     else: month = G - 13
     if month > 2.5: year = D - 4716
     else: year = D - 4715
     return year, month, day




##############################
##
##  RDS handling functionality
##
##############################

rds_old=[0]*4   # detect duplicates




SCAN_NAME_TIMEOUT=500   # max number of 5-millisecond intervals to check



def rdsloop_getstationname(channel,radio,minreads=300,mingrps=80):
    station_name=''
    rdscnt=0
    if True: # get station name from RDS, group 0A
      for t in range(0,max(SCAN_NAME_TIMEOUT,minreads)):
        sleep(0.005)
        radio.si4703ReadRegisters()
        if radio.isrds(): handlerds(channel,radio,out=False);rdscnt+=1
        station_name=rds_getmem('0A',quot='')
        if (t>minreads and rdscnt>mingrps) or (rdscnt<2 and t>100):
          if '_' not in station_name: break
          if rdscnt<2 and t>100: break # do not wait when there are no data
      #station_name=station_name.strip()
    return station_name,t,rdscnt


def stations_scan(radio,getrdsname=True,prefix='',verb=True,out=True,getrds=True):
    channel=radio.si4703GetChannel()
    #firstchan=channel
    #through=False
    chans={}

    if out and verb: print('scan start');print('          freq  rssi      name      badgrp  seen RDS group counts')
    """ scan start
        freq  rssi      name      badgrp  seen RDS group counts
STATION:  89.5 14    [COUNTRY ]    --:0   0A:20  2A:20 10A:20
STATION:  90.3 12    [EXPRESFM]    --:10  0A:45  2A:5
STATION:  92.6  4    [R-PLUS  ]    --:52  0A:6   2A:1   8A:1
STATION:  93.7 13    [CITY 937]    --:2   0A:36  2A:18  3A:2  11A:2
STATION:  94.1 11    [  FAJN  ]    --:5   0A:34  2A:17  3A:2  11A:2
STATION:  94.6  3    [R-ZURNAL]    --:0   0A:30  1A:5   2A:7   3A:4   8A:11
STATION:  95.3 15    [  BEAT  ]    --:0   0A:20  2A:20 10A:19
STATION:  95.7 13    [ SIGNAL ]    --:1   0A:29  2A:30
STATION:  96.6  3    [ IMPULS ]    --:13  0A:32  2A:15
STATION:  98.6 14    [CLASSIC ]    --:0   0A:54  2A:6
STATION:  98.7 14    [CLASSIC ]    --:0   0A:53  2A:7
STATION: 105.0  0    [R-VLTAVA]    --:0   0A:40  2A:10 14A:10
scan end """

    while True:
      rds_initstr()
      station_name=''
      rdscnt=0

      if channel!=FREQ_FROM and channel!=FREQ_TO: # ends, where the scan stops and there are no data
        if out: p(prefix+'STATION: '+getchanrssi(channel,radio,spacer='  '))
        if getrdsname:
          if getrds: station_name,timespent,rdscnt=rdsloop_getstationname(channel,radio,minreads=500,mingrps=80)
          else:      station_name,timespent,rdscnt=rdsloop_getstationname(channel,radio,minreads=100,mingrps=30)
        if out: p('  ['+station_name+']')
        #if out: p('  '+str(timespent)+','+str(rdscnt))
        if getrds and out:
          p('   ')
          for x in natsort(rds_stat): p(f'{x: >3}:{rds_stat[x]: <3}')

          for x in rds_odagrps:
            #if rds_odagrpscnt[x]/tot>=thresh:
              p('  ODA:'+x+':'+str(rds_odagrpscnt[x])+':'+rds_getodagrpname(x,threshold=0))

        #p(' ');p(rds_stat)
        if out: print()
      chans[channel]=station_name
      radio.si4703SeekUp(out=False)
      channel=radio.si4703GetChannel()
      #print(chans)
      if channel in chans: # already seen
        if out and verb: print('scan end')
        break
    return chans





# take the array of 4 2-bit correction numbers, get thresholds
def rds_isbad(corr,threshold=2):
    for x in range(threshold,4):
      if x in corr: return True
    return False


rds_tmcrecord=None
rds_tmclist={}

def rds_tmclist_reset():
    global rds_tmclist
    rds_tmclist={}

def rds_tmclist_add(loc,event,direc,raw,partial=False,out=False):
    #key=hexstr(loc)+':'+hexstr(event,l=3)+':'+str(direc)
    key=hexstr(event,l=3)+':'+hexstr(loc)+':'+str(direc)
    if key in rds_tmclist:
      if partial:
        #if out: p(':::PARTIAL')
        return # allow inserting a partial record if not existing yet
      cnt=rds_tmclist[key]['cnt']
    else: cnt=0
    rds_tmclist[key]={'raw':raw,'when':monotonic(),'cnt':cnt+1}

def rds_tmclist_show():
    for key in sorted(rds_tmclist.keys()):
      tmc=rds_tmclist[key]
      #p(key+' -')
      p(f'{key} {tmc["cnt"]:3}x ')
      #p(' '+str(tmc['cnt'])+'x ')
      age=round(monotonic()-tmc['when'])
      if(age<60): p(f'{age:2}s')
      else: p(f'{round(age/60):2}m')
      p(':')
      rds_tmc_decode(tmc['raw'],show=True)
      print()


def rds_tmc_decode(rds,out=True,show=False):
    VARY=getbits(rds[1],0,5)
    F=getbit(VARY,3) # F bit, 1=singlegrp,0=multigrp
    D=getbit(rds[2],15)
    single=F
    multi_first=D
    #if not out: return # for now; add caching decoded sentences later
    if out:
      #p(' L='+str(len(rds)))
      if len(rds)==4:
        p([' m',' S'][single])
        if not single: p(' 1st')
        if single: p(' duration=')
        else: p(' cont=')
        p(str(getbits(VARY,0,3)))
      elif show: p(' m')
    event=getbits(rds[2],0,11)
    loc=rds[3]
    direc=getbit(rds[2],14)
    if not show:
      if (single or len(rds)>4): rds_tmclist_add(loc,event,direc,rds,out=out,partial=False)
      else:                      rds_tmclist_add(loc,event,direc,rds,out=out,partial=True)
    if out:
      p(' divert='+str(D))
      p(' dir='+['0','1'][getbit(rds[2],14)])
      p(' extent='+str(getbits(rds[2],11,3)))
      #p(' event='+str(event)) # https://github.com/bastibl/gr-rds/blob/maint-3.10/lib/tmc_events.h
      p(' event='+f'{event:4}') # https://github.com/bastibl/gr-rds/blob/maint-3.10/lib/tmc_events.h
      #p('/x'+hexstr(getbits(rds[2],0,11),l=3)) # https://github.com/bastibl/gr-rds/blob/maint-3.10/lib/tmc_events.h
      p(' loc='+hexstr(loc))
#      if single or len(rds)>4:
      if event in RDS_TMC_EVENTS: p(' ['+RDS_TMC_EVENTS[event]+']')
    if not out: return # only output follows
    if len(rds)==4:
      if F==0: p(' [PARTIAL]')
      return # only first group

    # decode additional data here
    bitstr=''
    for t in range(2,int(len(rds)/2)):
      #p(':');p(hexstr(rds[2*t],l=3))
      #p(':');p(hexstr(rds[2*t+1]))
      bitstr+=f'{rds[2*t]:012b}{rds[2*t+1]:016b}'
    #p(bitstr)
    #print()
    label_len=[3, 3, 5, 5, 5, 8, 8, 8, 8, 11, 16, 16, 16, 16, 0, 0]
    auxarr=[]
    dataarr=[]
    #print();print(bitstr)
    while bitstr!='':
      label=int(bitstr[:4],2)
      if label==0: break
      bitstr=bitstr[4:]
      l=label_len[label]
      databitstr=bitstr[:l]
      auxarr.append(f'{label}={l}:{databitstr}')
      try: data=int(databitstr,2)
      except: data=0
      bitstr=bitstr[l:]
      #print('  label',label,'len',l,'data',data,databitstr)
      if label==15: continue
      if label==0 and data==0: continue
      dataarr.append(data)
    p(' aux='+str(dataarr).replace(' ',''))
    if VERB: p(' '+str(auxarr))


def rds_tmcreset():
    global rds_tmcrecord
    rds_tmcrecord={'raw':[],'contid':-1,'seqid':-1,'num':0}

def rds_tmcadd(rds,isfirst,out=True):
    if rds_tmcrecord==None or isfirst: rds_tmcreset()
    VARY=getbits(rds[1],0,5)
    if isfirst:
      rds_tmcrecord['contid']=getbits(VARY,0,3)
      rds_tmcrecord['num']=1
      rds_tmcrecord['raw']=rds.copy()
      return
    if rds_tmcrecord['contid']!=getbits(VARY,0,3): return # skipped
    is2nd=getbit(rds[2],14) # second
    seqid=getbits(rds[2],12,2)
    if is2nd and rds_tmcrecord['num']!=1 and seqid!=0: return
    if is2nd:
      rds_tmcrecord['num']=2
      rds_tmcrecord['seqid']=seqid
      rds_tmcrecord['raw'].append(rds[2]&0xfff)
      rds_tmcrecord['raw'].append(rds[3])
      if seqid==0: # finished multigroup
        rds_tmc_decode(rds_tmcrecord['raw'],out=out)
        return
    if rds_tmcrecord['seqid']-1 != seqid: return
    rds_tmcrecord['seqid']=seqid
    rds_tmcrecord['raw'].append(rds[2]&0xfff)
    rds_tmcrecord['raw'].append(rds[3])
    if seqid==0: # finished multigroup
      rds_tmc_decode(rds_tmcrecord['raw'],out=out)


# handle RDS message, filter, parse data to show
def handlerds(channel,r,skipgrp=[],onlygrp=[],raw=None,corrthreshold=2,out=True,outfixed=True,eraseline='',lastgrp=''):
    global rds_old,rds_pty,rds_pic

    if raw!=None:
      rds=raw
      corr=[0,0,0,0]

    else:
      rds,corr=r.getrds()
      if rds==rds_old:
        #print('dup')
        return False,lastgrp
      rds_old=rds

    PIC=rds[0]
    GTYPE=rds[1]>>12
#    B0=(rds[1] & 0x0800) >> 11
#    TP=(rds[1] & 0x0400) >> 10
    B0=getbit(rds[1],11)
    TP=getbit(rds[1],10)
#    xPTY=(rds[1]>>5)&0x1F
#    xVARY=rds[1]&0x1F
    PTY=getbits(rds[1],5,5)
    VARY=getbits(rds[1],0,5)
    gtypestr=getrdsgtype(GTYPE,B0)
    corrsum=sum(corr)
    rds_pty=PTY
    rds_pic=PIC

    if not rds_isbad(corr,threshold=corrthreshold): rds_stat_add(gtypestr,GTYPE,B0)
    #if not out: return False # count stats but do not show anything

    # group filtering
    if onlygrp!=[]:
      if rds_isbad(corr): return False,'--' # do not show bad packets in group
      if gtypestr not in onlygrp: out=False
    elif skipgrp!=[]:
      if rds_isbad(corr): return False,'--' # do not show bad packets in group
      if gtypestr in skipgrp: out=False

    # print line prefix, correction flags, return if too corrupted blocks
    if raw==None:
      if out:
        p(eraseline)
        printchanrssi(channel,r)
        for i in corr: p(i)
        p('  '+':'.join(f'{i:04x}' for i in rds)+' ')
      if rds_isbad(corr,threshold=corrthreshold): # if uncorrectable block or suspicious block with group ID
        if out: print(' bad blocks, skipping')
        rds_stat_add('--',-1,0)
        return out,gtypestr
    else: # print raw dump
      if out: p(':'.join(f'{i:04x}' for i in rds)+' ')

    # print fixed packet prefixes
    if out:
      if outfixed:
        p(' PIC='+hexstr(PIC))
        p(' TP='+str(TP))
        p(' PTY='+str(PTY))
        p(' VARY='+hexstr(VARY,l=2))
        p('  GTYPE='+(rdslist_get_grpdesc(gtypestr)+'                          ')[:16])
      else: p(f' {gtypestr:>3} ')


    # individual types handling

    # http://www.g.laroche.free.fr/english/rds/groupes/0/groupe0A.htm
    if GTYPE==0:
      addr=getbits(rds[1],0,2)
      if B0==0: rds_setstrraw('DI',0x30+getbit(rds[1],2),addr);
      rds_setstr('0A',rds[3],addr,out=False)
      if B0==0: # group A
        islowfreq=rds_byte2freq_add(rds[2]>>8,'0A',isfm=True)
        rds_byte2freq_add(rds[2]&0xff,'0A',isfm=not islowfreq)
      if out:
        p(' TA='+str(getbit(rds[1],4)))
        p(' MS='+str(getbit(rds[1],3)))
        p(' DI='+str(getbit(rds[1],2)))
        p(' C='+str(addr))
        if B0==0: # group A
          p(' ');rds_setstr('0A',rds[3],addr,out=out)
          p(' ['+str(bytes([rds[3]>>8,rds[3]&0xff]))+']')
          p(' Dx='+rds_mem['DI'].decode('utf-8'))
          #if B0==0: # group A
          p(' AF='+rds_byte2freq(rds[2]>>8))
          p(' AF='+rds_byte2freq(rds[2]&0xff))
        else: # group B
          p(' PI='+hexstr(rds[2]))
          # if out: p(   '/'+str(bytes([rds[2]>>8,rds[2]&0xff]))+']')
          p(' ['+str(bytes([rds[3]>>8,rds[3]&0xff]))+']')


    # http://www.g.laroche.free.fr/english/rds/groupes/1/groupe1A.htm
    elif gtypestr=='1A':
      if out: p(' '+hexpayload(rds))


    elif GTYPE==2: # only either 2A or 2B can be present; 64 or two 32 byte strings
      addr=getbits(rds[1],0,4)
      if out: p(' '+('0'+str(addr))[-2:])
      if out: p(' '+ints2str(rds[2],rds[3]).replace('\r','\\r'))
      if out: p(' ')
      rds_setstr2('2',rds[2],rds[3],addr,out=out)


    elif gtypestr=='3A':
      msg=rds[2]
      appid=rds[3]
      odagrp=str(getbits(VARY,1,4))+['A','B'][getbit(VARY,0)]

      if odagrp in rds_odagrps:
        if corrsum<2: # at most one correction
          rds_setodagrp(odagrp,appid)
      else:
        # for now, force always including to test handling spurious data
        if True or 2 not in corr and 3 not in corr: rds_setodagrp(odagrp,appid)
      if out:
        p(' '+hexpayload(rds))
        p(' grp=')
        if VARY==0: p('[0=notcarried]')
        elif VARY==0x1f: p('[1F=encoderError]')
        else: p(odagrp)
          #p(str(getbits(VARY,1,4)))
          #p(['A','B'][getbit(VARY,0)])
        p(' msg='+hexstr(msg)) # section 7.5.2.2 of ISO 14819-1
        p(' appId='+hexstr(appid))
        p(rdslist_get_ODA_AID_name(appid))
        #if appid==0xcd45: p('(RDS-TMS ALERT-C test)')
        #if appid==0xcd46: p('(RDS-TMS ALERT-C)')
        #if appid==0x4bd7: p('(RT+)') # https://tech.ebu.ch/docs/techreview/trev_307-radiotext.pdf

#APPID_TMC=0xCD46
#APPID_RTPLUS=0x4BD7


      # RDS TMC
      if appid==ODAAID_TMC or appid==0xcd45: # 0xcd46 # https://github.com/bastibl/gr-rds/blob/maint-3.10/lib/parser_impl.cc
        varcode=(msg>>14)&3
        #if corrsum==0: rds_setodagrp(odagrp,'TMC')
        #rds_odagrps[odagrp]='TMC'
        if out: p(' varcode='+str(varcode))
        if varcode==0:
          if out:
            p(' loctable='+hexstr((msg>>6)&0x3f))
            p(' altfreq='+str(getbit(msg,5)))
            p(' transmode='+str(getbit(msg,4)))
            p(' internat='+str(getbit(msg,3)))
            p(' national='+str(getbit(msg,2)))
            p(' regional='+str(getbit(msg,1)))
            p(' urban='+str(getbit(msg,0)))
        elif varcode==1:
          g=(msg>>12)&3
          if out:
            p(' gap='+str(g))
            p('(=>'+['3','5','8','11'][g]+')')
            p(' serviceId='+hexstr((msg>>6)&0x3f))

      # RDS RT+
      elif appid==ODAAID_RTPLUS: #0x4bd7: # https://github.com/bastibl/gr-rds/blob/maint-3.10/lib/parser_impl.cc
        #if corrsum==0: rds_setodagrp(odagrp,'RT+')
        #rds_odagrps[odagrp]='RT+'
        if out:
          p(' rfu='+hexstr(msg>>13,l=1))
          p(' cb='+str(getbit(msg,12)))
          p(' scb=x'+hexstr(getbits(msg,8,4),l=1))
          p(' template=x'+hexstr(getbits(msg,0,8),l=2))

      else:
        #if corrsum==0: rds_setodagrp(odagrp,'0x'+hexstr(appid))
        if corrsum==0: rds_setodagrp(odagrp,appid)
    # stop further processing 
    #elif not out: return False,gtypestr


    # http://www.g.laroche.free.fr/english/rds/groupes/4/groupe4A.htm
    # 1050   5  0000  232d:40e1:d6de:3540  PIC=232d TP=0 PTY=7 VARY=0001 GTYPE=4A:clock         01:d6de:3540 julday=60271 3:21 +0  # 2023-11-23 03:21
    elif gtypestr=='4A':
      i=rds_to_raw(rds)
      julday=getbits_long(i,17,17)
      hr=getbits_long(i,12,5)
      mn=int(getbits_long(i,6,6))
      offssgn=getbit(i,5)
      offs=getbits_long(i,0,5)
      yr,mon,day=julianday_to_date(julday,modified=True) # conversion from modified julian day to julian day
      #p(' = ')
      s=f'{yr}-{mon:02}-{floor(day):02} {hr:02}:{mn:02}'
      #s=str(yr)+'-'+str(mon)+'-'+str(int(day))+' '+('0'+str(hr))[-2:]+':'+('0'+str(mn))[-2:]
      rds_setstrstr('clock',s)
      if out:
        p(' '+s)
        p('   offs='+['+','-'][offssgn]+str(offs))
        p(' julday='+str(julday))
        #p(' raw='+hexpayload(rds))

    # https://www.automa.cz/cz/casopis-clanky/dynamicka-navigace-ve-vozidle-rds-tmc-2003_07_28880_3079/
    # http://www.g.laroche.free.fr/english/rds/groupes/8/groupe8A.htm
    # https://www.vut.cz/www_base/zav_prace_soubor_verejne.php?file_id=116618
    # https://github.com/gjasny/v4l-utils/blob/master/lib/libv4l2rds/libv4l2rds.c   !!!
    #elif rds_getodagrp(gtypestr)=='TMC' or  gtypestr=='8A':
    elif rds_getodagrp(gtypestr)==ODAAID_TMC or  gtypestr=='8A':
      #if out: p(' '+hexpayload(rds))
      if out: p(' ODA:TMC:')
      T=getbit(VARY,4) # T bit, 1=TuningInfo,0=UserMessage
      F=getbit(VARY,3) # F bit, 1=singlegrp,0=multigrp
      D=getbit(rds[2],15)
      #p('+');p(T);p(F);p(D)
      if T==1:
        var=VARY&0x0F
        if out:
          p(' tuningInfo')
          p(' var='+str(var))
          if var==4 or var==5: #
            p(' info='+ints2str(rds[2],rds[3]))
        if var==4 or var==5:
          if out: p(' ')
          rds_setstr2('TMCID',rds[2],rds[3],var-4,out=out)
        if out:
          if var==6: p(': specific freqs for same RDS-TMC on stations with different PI code') # todo: add frequencies
          if var==7: p(': mapped freq pairs to use if tuned to tuning freq')
          if var==8: p(': up to 2 PI codes for adjanced networks') # carrying the same RDS-TMC service on all transmitters of the network
          if var==9: p(': PI codes of networks with different system parameters')
      else:
        #if out: # no memory processing, just showing data
          if out: p(' msg')
          #p([' multi',' single'][F])
          if F==1 or D==1:
            rds_tmc_decode(rds,out=out)
            rds_tmcadd(rds,True,out=out)
          else:
            if out:
              if getbit(rds[2],14): p(' 2nd')
              else: p(' 3r+')
              p(' cont='+str(getbits(VARY,0,3)))
              #p(' 2ndGrp='+str(getbit(rds[2],14))) # msbC&0x40
              p(' seq='+str(getbits(rds[2],12,2)))
              #if getbits(rds[2],12,2)==0: p('(complete)')
              p(' data='+hexstr(rds[2],l=3)+':'+hexstr(rds[3]))
            rds_tmcadd(rds,False,out=out)

    # http://www.g.laroche.free.fr/english/rds/groupes/10/groupe10A.htm
    elif gtypestr=='10A':
      addr=VARY&0x01
      if out:
        p(' '+['A','B'][getbit(VARY,4)])
        p(' addr='+str(addr))
      rds_setstr2('PTYN',rds[2],rds[3],addr,out=out)

    # http://www.g.laroche.free.fr/english/rds/groupes/14/groupe14A.htm
    elif gtypestr=='14A':
      addr=VARY&0x0f
      if addr==4:
        rds_byte2freq_add(rds[2]>>8,'14A',isfm=True)
        rds_byte2freq_add(rds[2]&0xff,'14A',isfm=True)
      if out:
        p(' TPon='+str(getbit(VARY,4)))
        p(' var='+str(addr))
        if addr<4:
          p(' DATA='+int2str(rds[2]))
        elif addr==4:
          p(' AFon='+rds_byte2freq(rds[2]>>8))
          p(' AFon='+rds_byte2freq(rds[2]&0xff))
        elif addr==13:
          p(' PTYon='+str(getbits(rds[2],11,5)))
          p(' TAon='+str(getbit(rds[2],0)))
          p(' data='+hexstr(rds[2]))
        else:
          p(' DATA='+hexstr(rds[2]))
        p(' PIon='+hexstr(rds[3]))


    # https://tech.ebu.ch/docs/techreview/trev_307-radiotext.pdf
    elif rds_getodagrp(gtypestr)==ODAAID_RTPLUS:
      arr=rds_to_raw(rds)
      if out:
        def getrttype(n):
          return '('+RDSPLUS_TAGS[n]+')'
#          if n==1: return('(title)')
#          if n==2: return('(album)')
#          if n==4: return('(artist)')
#          return ''
        p(' ODA:RT+:')
        p(' toggle='+str(getbits_long(arr,36,1)))
        p(' run='+str(getbits_long(arr,35,1)))
        conttype=getbits_long(arr,29,6);start=getbits_long(arr,23,6);leng=getbits_long(arr,17,6)
        p(f' tag1={conttype}({RDSPLUS_TAGS[conttype]})@{start}[{leng}]')
        #p(' tag1='+str(conttype)+getrttype(conttype)+'@'+str(start)+'['+str(leng)+']')
        conttype=getbits_long(arr,11,6);start=getbits_long(arr,5,6);leng=getbits_long(arr,0,5)
        p(f' tag2={conttype}({RDSPLUS_TAGS[conttype]})@{start}[{leng}]')
        #p(' tag2='+str(conttype)+getrttype(conttype)+'@'+str(start)+'['+str(leng)+']')


    else:
      if out:
        p(' '+hexpayload(rds))
        s=rds_getodagrpname(gtypestr)
        if s!='': p(' ODAAID='+s)


    if out: print()
    return out,gtypestr



#############################
##
##  interactive functionality
##
#############################

def stat_getsorted(): # TODO, do it way more elegant
  keys=list(rds_stat.keys())
  return natsort(keys)
#  for x in range(0,len(keys)):
#    if len(keys[x])<3: keys[x]='-'+keys[x] # crude hack for natural sort
 # keys=sorted(keys)
  #for x in range(0,len(keys)):
#    if keys[x][0]=='-': keys[x]=keys[x][1:]
#  return keys

grp0A_D_names=[ {'0':'PTYstatic','1':'PTYdynamic'},{'0':'notCompressed','1':'compressed'},{'0':'noArtHead','1':'artificialHead'},{'0':'mono','1':'stereo'} ]

def printmemstat():
    def showstat(x,frac):
        p('  ['+x+' '+str(rds_stat[x]))
        p('x '+str(round(100*frac,1))+'%]')

    # RDS memory strings
    for x in rds_mem:
      p('  '+(x+' '*7)[:7])
      rds_printmem(x)
      if x=='DI':
        p(' ')
        s=rds_mem[x]
        #p(names)
        for x in range(0,4):
          n=chr(s[x])
          if n in grp0A_D_names[x]:
            p('  '+grp0A_D_names[x][n])
      print()

    if rds_pic>=0:
      p(f'  PIC:   {rds_pic:04x}')
      ctry=getbits(rds_pic,12,4)
      area=getbits(rds_pic,8,4)
      p(f'  country={ctry} area={area}({RDS_PI_AREADESC[area]}) program={rds_pic&0xff}')
      print()
    if rds_pic>=0:
      p(f'  PTY:   {rds_pty}')
      p(' = '+RDS_RBDS_PTY_TYPES[rds_pty][RDS_RBDS])
      print()

    # groups statistics
    tot=sum(rds_stat.values())
    tot2=tot
    if '--' in rds_stat: tot2-=rds_stat['--']
    isbad=False
    threshold=0.02 # 2%
    p('  stat:')
    if tot>0:
      for x in stat_getsorted():
        if x=='--': frac=rds_stat[x]/tot
        else:       frac=rds_stat[x]/tot2
        if x=='--' or x=='4A' or frac>=threshold: showstat(x,frac)
        else: isbad=True
      if isbad:
        print()
        p('  stat:  suspected bad:')
        for x in stat_getsorted():
          if x=='--' or x=='4A': continue
          frac=rds_stat[x]/tot2
          if frac < threshold: showstat(x,frac)
    print()

    # ODA group assign stats
    tot=sum(rds_odagrpscnt.values())
    thresh=0.05
    isbad=False
    p('  ODA: ')
    if tot>0:
      for x in rds_odagrps:
        if rds_odagrpscnt[x]/tot>=thresh:
          p('  ['+x+' '+rds_getodagrpname(x,threshold=0))
          p(' '+str(rds_odagrpscnt[x]))
          p('x]')
        else: isbad=True
    if isbad:
      print()
      p('  ODA:   suspected bad:')
      for x in rds_odagrps:
        if rds_odagrpscnt[x]/tot<thresh:
          p('  ['+x+' '+rds_getodagrpname(x,threshold=0))
          p(' '+str(rds_odagrpscnt[x]))
          p('x]')
      #p('    [');p(rds_odagrps);p('] ');p(rds_odagrpscnt) # debug
    print()

    def pfreq(f):
      #p('XXX'+str(f))
      #p(' ['+f['freq']+' '+str(f['cnt'])+'x]')
      p(' '+f['freq'])
    def pfreqs(grp):
      if grp not in rds_freq: return
      p(' '+grp+':')
      tot=0
      for x in rds_freq[grp]: tot+=rds_freq[grp][x]['cnt']
      for x in natsort(rds_freq[grp].keys()):
         if rds_freq[grp][x]['cnt']/tot >0.05: pfreq(rds_freq[grp][x])
    for x in rds_freq:
      if x=='count': continue
      if x in rds_freq:
        p('altfreq:')
        pfreqs(x)
        if x=='0A': p(' count='+str(rds_freq['count']))
      print()

    if len(rds_tmclist)>0:
      print('TMCseen:',len(rds_tmclist))

#    if '14A' in rds_freq:
#      p('altfreq:')
#      pfreqs('14A')
##    for x in rds_freq:
##      if x=='count': continue
##      for y in rds_freq[x]:  print('freq:',x,y,rds_freq[x][y])
#      print()


# get RDS group statistics as single line
def getrdsgrpstat():
    s=''
    for x in stat_getsorted():
      if s!='': s+=' '
      s+=x+':'+str(rds_stat[x])
    return s


# print volume from chip
def printvol(radio):
    print('volume:',radio.si4703GetVolume())


# interactive help
def help_interactive():
  print()
  print("""
Keyboard keypress controls:
===========================

<space> pause/resume output
  - +   volume
  [ ]   prev/next station
  ?     help
  f     filter RDS, hide 0A and 2A "spam"
  h     hide/show fixed header

  g     toggle 2A radiotext string vs group stats
  s     show RDS string buffers
  t     show RDS-TMC traffic data log

  S     stations scan

  i     reset/initialize chip
  I     powerdown chip
  r     show chip registers

  q     quit, switch off radio
  Q     quit, keep radio running

status line format:
freq RSSI "station" state current-group seen-groups "radiotext"/stats [<paused/filtered>]
state can be P for paused, F for filtering, R flashing when group was received
""")

  print()
  print('Filters:',RDS_FILTERS)
  print()

# main interactive loop
def main(init=False,deinit=ONCRASH_OFF):
    # device ID is typically 0x10 - confirm with "sudo i2cdetect 1"
    # I2C_addr, GPIO_RESET, GPIO_INT(GPIO2)
    try: COLS=get_terminal_size().columns
    except: COLS=80

    rds_initstr()
    radio = getradio()
    printreg(radio)
    channel=0

    if init or not radio.si4703isInitialized():
      radio.si4703Init()
    else: radio.si4703InitPwr()

    radio.print_version()
    printvol(radio)

    #print('COLS:',COLS)
    eraseline=' '*(COLS-2)+'\r'

    radio_off=deinit  # do not silence when crashing
    showrds=True      # show every RDS packet in scrolling view
    showgrpstat=False # show group stats instead of long 2A string
    rdsskipgrp=[]     # filter of groups to not show
    rdsonlygrp=[]     # filter of groups to only show
    filteridx=0       # selected filter index
    outfixed=False    # output the fixed group from rds[0,1]

    nogrp=0           # counter of no-RDS-data, to hide last group
    lastgrp=''        # last group received, ephemeral, shown on status line

    channel=radio.si4703GetChannel()

    print('ready')
    # do not block input, for immediate keypress handling
    with raw(stdin):
     with nonblocking(stdin):
      try:
       while True:
        sleep(0.002)
        radio.si4703ReadRegisters()

        noshowrow=False
        isrds=radio.isrds()
        if isrds:
          noshowrow,lastgrp=handlerds(channel,radio,skipgrp=rdsskipgrp,onlygrp=rdsonlygrp,out=showrds,outfixed=outfixed,eraseline=eraseline,lastgrp=lastgrp)
          nogrp=0
        else: nogrp+=1
        if nogrp>50: lastgrp=''
        if not noshowrow:
          s=getchanrssi(channel,radio)
          s+=rds_getmem('0A')+' ' # show short station ID
          if not showrds:      s+=['P','R'][isrds] # is paused
          elif rdsskipgrp!=[]: s+=['F','R'][isrds] # is filtered
          else: s+=' '                             # is running
          s+=('    '+lastgrp)[-4:]
          s+=' '+rds_get_quickgroups() # what groups were shown
          s+='  '
          if showgrpstat: s+='['+getrdsgrpstat()+']'
          else: s+=rds_getmem('2') # show long station data
          if not showrds: s+=' <paused>'
          elif rdsskipgrp!=[]: s+=' <filtered:'+','.join(rdsskipgrp)+'>'
          p(s[:COLS-2]+'\r')
          #print()

        # read character
        # TODO: can be spliced with HTTP or MQTT control if needed
        cmd = stdin.read(1)
        if cmd=='': continue

        # erase current realtime-data line
        #p(' '*30+'\r')
        p(eraseline) # terminal screen width

        # pause/resume
        if cmd==' ':
            showrds= not showrds
        # console command help
        elif cmd == "?":
            showrds=False
            help_interactive()

        # tune seek down
        elif cmd in ['[',']']:
            p('tuning\r')
            if cmd=='[': radio.si4703SeekDown()
            else: radio.si4703SeekUp()
            rds_initstr()
            lastgrp=''
            channel=radio.si4703GetChannel()

        # volume down
        elif cmd == "-":
            radio.si4703SetVolume(radio.si4703GetVolume()-1)
            printvol(radio)
        # volume up
        elif cmd == "+" or cmd == "=":
            radio.si4703SetVolume(radio.si4703GetVolume()+1)
            printvol(radio)

        # cycle or reset RDS filters
        elif cmd=="f" or cmd=="F":
            if cmd=='F': filteridx=0
            else: filteridx=(filteridx+1)%len(RDS_FILTERS)
            rdsskipgrp=RDS_FILTERS[filteridx]
            if rdsskipgrp==[]: print('--- filter off')
            else:              print('--- filter on:',rdsskipgrp)
            rdsonlygrp=[]
            #print(rdsskipgrp)
            for x in rdsskipgrp:
              if x[0]=='=': rdsonlygrp.append(x[1:])
            #print('filter:','-',rdsskipgrp,'+',rdsonlygrp)

        elif cmd=='g':
            showgrpstat=not showgrpstat

        elif cmd=='h':
            outfixed=not outfixed

        # show RDS memory strings
        elif cmd == "s":
            print()
            printmemstat()
            print()

        elif cmd == "t":
            print()
            rds_tmclist_show()
            print()

        # dump chip registers
        elif cmd == "r":
            printreg()
            print()
        # reset/initialize chip
        elif cmd == "i":
            radio.si4703Init()
            rds_initstr()
            lastgrp=''
            channel=radio.si4703GetChannel()
        # shutdown/poweroff chip
        elif cmd == "I":
            radio.si4703ShutDown()

        elif cmd == "S":
            stations_scan(radio)
            channel=radio.si4703GetChannel()

        # quit, shut down radio
        elif cmd == "q":
            print()
            printmemstat()
            radio_off=True
            break
        # quit, keep radio running
        elif cmd == "Q":
            print()
            printmemstat()
            radio_off=False
            break

      except KeyboardInterrupt:
        radio_off=False
        print("Exiting program")
      finally:
        print(' '*20)
        if radio_off:
          print("Shutting down radio")
          radio.si4703ShutDown()
        else: print("Exiting, keeping radio")
        print()




#########################################
##
##  noninteractive parse of RDS-Spy dumps
##
#########################################

def main_stdin(out=True,stat=True,tmc=True):
    rds_initstr()
    while True:
      try:
        s=stdin.readline()
      except KeyboardInterrupt:
        break
      except: continue
      if s=='': break
      a=s.strip().split(' ')
      i=[0]*4
      if len(a)<4: continue
      fail=False
      for x in range(0,4):
        if '-' in a[x]: fail=True;break
        if len(a[x])!=4: fail=True;break
        try: i[x]=int(a[x],16)
        except: fail=True;break
      if fail: continue
      #print(':',a,i)
      handlerds(0,None,raw=i,out=out)


    if tmc:
      if len(rds_tmclist)>0:
        if out: print()
        rds_tmclist_show()
    if stat:
      if out or tmc: print()
      printmemstat()



# run the station-scan loop
def main_scan(init=False,deinit=False,getrdsname=True,verb=False):
    radio = getradio()
    if init or not radio.si4703isInitialized():
      radio.si4703Init(verb=verb); # double init, for some reason it is needed
      radio.si4703Init(verb=verb);
    else: radio.si4703InitPwr()
    radio.si4703InitPwr()
    stations_scan(radio,getrdsname=getrdsname)
    if deinit:
      if verb: print();print('chip power-off')
      radio.si4703ShutDown(verb=verb)



# read RDS registers and correction flags, output timestamped hex lines
def handlerds_dump(radio,corrthreshold=3):
    from datetime import datetime
    global rds_old

    rds,corr=radio.getrds()
    if rds==rds_old: return # skip duplicates
    rds_old=rds

    s=':'.join(f'{i:04x}' for i in rds)
    sa=s.split(':')
    for t in range(0,4):
      if corr[t]>corrthreshold: sa[t]='----'
    if sa==['----']*4: return # skip all-bad groups

    p(' '.join(sa).upper())
    p(' @')
    print((str(datetime.utcnow()).replace('-','/'))[:22] )


# RDS logs: https://github.com/walczakp/rds-spy-logs
# RDS SPY: http://rdsspy.com/download/mainapp/rdsspy.pdf
# example format:
"""
FE37 2415 2020 2020 @2018/01/02 19:20:13.56
FE37 0409 E273 5449 @2018/01/02 19:20:13.65
FE37 3410 0746 CD46 @2018/01/02 19:20:14.24
"""


# run the data dumping loop
def main_dump(init=False,initwait=False,corrthreshold=2,getrdsname=True,printheader=True,verb=False):
    rds_initstr()
    radio = getradio()
    if init or not radio.si4703isInitialized(): radio.si4703Init(verb=verb)
    else: radio.si4703InitPwr()
    channel=radio.si4703GetChannel()
    station_name=''

    if getrdsname: # get station name from RDS, group 0A
      station_name,_,_=rdsloop_getstationname(channel,radio)
      if station_name=='_'*8: station_name=''

    if printheader: # print header with freq and datetime
      from datetime import datetime
      now=datetime.now()
      print(f'<recorder="Si4703-shad" date="{now:%Y-%m-%d}" time="{now:%H-%M-%S}" source="1" name="{station_name}" location="" notes="'+fmtfreq(channel,pad=' ').strip()+' MHz">')
    else:
      print('<recorder="Si4703-shad" date="2019-05-04" time="22-14-20" source="1" name="" location="" notes="">')

    try:
      while True:
        radio.si4703ReadRegisters()
        if radio.isrds(): handlerds_dump(radio)
    except KeyboardInterrupt:
      pass


# read RDS registers and correction flags, output timestamped hex lines
def handlerds_get_raw(radio,corrthreshold=3):
    from datetime import datetime
    global rds_old

    rds,corr=radio.getrds()
    if rds==rds_old: return False,[] # skip duplicates
    rds_old=rds

    for t in range(0,4):
      if corr[t]>corrthreshold: return False,[] # skip bad packets

    return True,rds


# RDS logs: https://github.com/walczakp/rds-spy-logs
# RDS SPY: http://rdsspy.com/download/mainapp/rdsspy.pdf
# example format:
"""
FE37 2415 2020 2020 @2018/01/02 19:20:13.56
FE37 0409 E273 5449 @2018/01/02 19:20:13.65
FE37 3410 0746 CD46 @2018/01/02 19:20:14.24
"""

# run the data dumping loop
def main_dump_pcap(init=False,initwait=False,corrthreshold=2,getrdsname=True,printheader=True,verb=False):
    from struct import pack
    from time import time

    # scapy
    rds_initstr()
    radio = getradio()
    if init or not radio.si4703isInitialized(): radio.si4703Init(verb=verb)
    else: radio.si4703InitPwr()
    channel=radio.si4703GetChannel()

    # output bytearray into stdout
    def out_bytearray(s): stdout.buffer.write(s)

    # output pcap file header
    def out_pcap_fileheader():
      out_bytearray(pack('@LHHLLLL',0xA1B2C3D4,2,4,0,0,65535,1))

    # output pcap packet header, l=total packet length
    def out_pcap_packetheader(l):
      now=time()
      secs=int(now)
      usec=int(1000000*(now-secs))
      out_bytearray(pack('@LLLL',secs,usec,l,l))

    # return bytearray() of packet made from RDS data, encapsulate to RFtap, to UDP, to IP, to ethernet
    def pcap_get_ethUdpRftapHeader(rds,datalink_type=265,freq=965):
      lenhdr_eth=14
      lenhdr_ip=20
      lenhdr_udp=8
      lenhdr_rftap=20 #5*4
      payloadlen=len(rds)*2 # array of big-endian words
      udp_payloadlen=payloadlen+lenhdr_rftap
      # ethernet
      arr=bytearray()
      arr+=pack('BBBBBB',10,2,2,2,2,2) # MAC dest
      arr+=pack('BBBBBB',10,1,1,1,1,1) # MAC src
      arr+=pack('BB',8,0) # payload IPv4

      # IPv4
      ipv4len=udp_payloadlen+lenhdr_udp+lenhdr_ip
      #                               vlen serv   totlength     ident   flags ttl UDP chksum  src_IP    dest_ip
      arr+=pack('>BBHBBBBBBHBBBBBBBB',0x45,0x00,   ipv4len,   0x12,0x34, 0,0, 255, 17,0x923e, 10,1,1,1, 10,2,2,2)

      # UDP
      #            srcport dstport      udp_leng           chksum
      arr+=pack('>HHHH',1,0xcb21,udp_payloadlen+lenhdr_udp,0x3319)

      # RFtap              magicmagicmagic    len(32bitwords) flags    datalinktype     nominal_freq
      arr+=pack('<BBBBHHLd',0x52,0x46,0x74,0x61,    5,        0x0005,  datalink_type, freq/10*1000000)

      for x in rds: arr+=pack('>H',x)
      return arr

    def dumprdspacket(rds):
      rawpacket=pcap_get_ethUdpRftapHeader(rds)
      out_pcap_packetheader(len(rawpacket)) # 4x 2 bytes, plus 4x 1 byte
      out_bytearray(rawpacket)

    #def dumprds_LINKTYPE_RDS(rds):
    #  out_pcap_packetheader(12) # 4x 2 bytes, plus 4x 1 byte
    #  for x in range(0,4): obin16big(rds[x])
    #  for x in [0,1,2,3]: obin8(x)

    try:
      out_pcap_fileheader()
      while True:
        radio.si4703ReadRegisters()
        if radio.isrds():
          ok,packet=handlerds_get_raw(radio)
          if not ok: continue
          #dumprds_LINKTYPE_RDS(packet)
          dumprdspacket(packet)
    except KeyboardInterrupt:
      pass




######################
##
##  configuration dump
##
######################

def printconfig(hw=True,forceinit=False,verb=False):
    print('Si4703 hardware configuration:')
    print()
    print(f'I2C address:     0x{Si4703_I2C_ADDR:02x} @ bus {I2C_BUS}, /dev/i2c-{I2C_BUS}')
    print(f'hardware:        {HARDWARE}')
    print(f'RESET pin (BCM): {PIN_RESET}')
    print(f'IRQ pin (BCM):   {PIN_IRQ}, GPIO2 on Si4703',end='')
    if PIN_IRQ<0: print(' (disabled, uses polling)')
    else: print()
    #print()
    #print('preset RDS filters: ',RDS_FILTERS)
    print()
    if not hw: return
    print('interrogating chip:')
#    if True:
    try:
#      print('forceinit:',forceinit)
      radio = getradio()
      if forceinit:
        if verb: print('chip reset and initialization')
        radio.si4703Init(verb=verb)
        sleep(0.05) # without sleep sometimes reads as uninitialized
      else: radio.si4703InitPwr()
      radio.si4703ReadRegisters()
      #exit(0)
      print()
      radio.print_version()
      print()
      radio.si4703printreg(hdr=True)

      print()
      print('channel:  ',radio.si4703GetChannel())
      print('volume:   ',radio.si4703GetVolume())

      if forceinit:
        if verb: print();print('chip power-off')
        radio.si4703ShutDown(verb=verb)
    except Exception as e:
      estr=str(e)
      print('ERROR: chip communication failed')
      print('ERROR:',estr)
      if '[Errno 2]' in estr: print('ERROR: invalid I2C bus?')
      elif not forceinit: print('ERROR: is the chip initialized? (try -ci)')
    print()



def help_commands():
  print("""si4703 FM radio RDS data handler
chip control commands submenu
Usage: """+argv[0]+""" cmd [command]

cmd getvol    get current volume
cmd getch     get current channel

cmd vol-      volume down
cmd vol+      volume up
cmd volmax    max volume

cmd ch-       seek channel down
cmd ch+       seek channel up
""")

def docommand(cmd,forceinit=False,verb=True):
  radio = getradio()
  if forceinit or cmd=='init':
    if verb: print('chip reset and initialization')
    radio.si4703Init(verb=verb)
    sleep(0.05) # without sleep sometimes reads as uninitialized
  else: radio.si4703InitPwr()
  if cmd=='vol-': 
    radio.si4703SetVolume(radio.si4703GetVolume()-1)
    printvol(radio)
  if cmd=='vol+': 
    radio.si4703SetVolume(radio.si4703GetVolume()+1)
    printvol(radio)
  if cmd=='volmax':
    radio.si4703SetVolume(15)
    printvol(radio)
  if cmd=='getvol':
    printvol(radio)
  if cmd=='ch-':
    radio.si4703SeekDown()
    channel=radio.si4703GetChannel()
    chan=radio.si4703GetChannel()
    print('freq='+fmtfreq(chan,pad=' '))
  if cmd=='ch+':
    radio.si4703SeekUp()
    chan=radio.si4703GetChannel()
    print('freq='+fmtfreq(chan,pad=' '))
  if cmd=='getch':
    chan=radio.si4703GetChannel()
    print('freq='+fmtfreq(chan,pad=' '))


#######################
##
## commandline handling
##
#######################

def help_args():
    print("""si4703 FM radio RDS data handler
Usage: """+argv[0]+""" [command] [arguments...]
Where:

    info       print expected hardware configuration
      -n       do not access hardware
      -i       force hardware init
      -v       verbose init (with -i)

    scan       perform scan of radio stations, list names and RDS groups encountered
      -i       force hardware init

    dump       connect to chip, dump raw data to stdout in rds-spy log format
      -n       skip attempt to get station name from RDS

    parse      read rds-spy raw data from stdin, parse, output to stdout
      -n       do not print parsed data (use with -s, -t)
      -s       print RDS statistics
      -t       print RDS-TMC data
      -v       some extra verbosity/debug data somewhere

    cmd <cmd>  command for the chip (volume up/down, seek up/down)
      -h       list of commands
      -i       force init

    help       print help (also -h, --help)
      -i       print interactive commands help instead of commandline

    <none>     enter interactive mode
      -i       force hardware init
""")


def getarg(n):
  if n>=len(argv): return ''
  return argv[n]

OUTSTAT=False
OUTTMC=False
OUTPARSE=True
DOINIT=False
GETRDSNAME=True
INFOHW=True
VERB=False

cmd=''
cmds=['dump','info','scan','parse','cmd','help','?']

if __name__ == "__main__":
  if '-s' in argv: OUTSTAT=True
  if '-t' in argv: OUTTMC=True
  if '-noout' in argv: OUTDUMP=False
  if '-i' in argv: DOINIT=True
  if '-n' in argv: GETRDSNAME=False;INFOHW=False;OUTPARSE=False
  if '-v' in argv: VERB=True

  for x in argv:
    if x in cmds: cmd=x

  if '-h' in argv or '--help' in argv or 'help' in argv:
    if DOINIT: help_interactive()
    elif 'cmd' in argv or '-hc' in argv: help_commands()
    else: help_args();
    exit(0)

  if cmd=='cmd': docommand(getarg(argv.index('cmd')+1),forceinit=DOINIT);exit(0)
  if cmd=='info': printconfig(hw=INFOHW,forceinit=DOINIT,verb=VERB);exit(0)
  if cmd=='scan': main_scan(init=DOINIT,deinit=DOINIT);exit(0)
  if cmd=='dump': main_dump(getrdsname=GETRDSNAME);exit(0)
  if cmd=='parse': main_stdin(out=OUTPARSE,stat=OUTSTAT,tmc=OUTTMC);exit(0)
  main(init=DOINIT)

#    if len(argv)>1:
#      if argv[1]=='-h' or argv[1]=='--help': help_args();exit(0)
#      if argv[1]=='-hi' or argv[1]=='--help-interactive': help_interactive();exit(0)
#
#      if argv[1]=='-': main_stdin();exit(0)
#
#      if argv[1]=='-dN': main_dump(getrdsname=False);exit(0)
#      if argv[1]=='-d': main_dump(getrdsname=True);exit(0)
#      if argv[1]=='-dp': main_dump_pcap();exit(0)
#
#      if argv[1]=='-c': printconfig();exit(0)
#      if argv[1]=='-cn': printconfig(hw=False);exit(0)
#      if argv[1]=='-ci': printconfig(forceinit=True);exit(0)
#      if argv[1]=='-civ': printconfig(forceinit=True,verb=True);exit(0)
#
#      if argv[1]=='-s': main_scan();exit(0)
#      if argv[1]=='-si': main_scan(init=True);exit(0)
#    main()


