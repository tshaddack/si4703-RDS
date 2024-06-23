#!/usr/bin/env python

# SI4703 Python Library
# (c) 2016 Ryan Edwards <ryan.edwards@gmail.com> 
# Ported from my Arduino library which was modified from Aaron Weiss @ SparkFun's original library
#
# Release Notes:
# 1.0    27-Mar-2016        Initial release
#
# To-do:
# Implement the remaining RDS data groups
# Add more try/execpt handling to catch errors
# 

import smbus
import time
import RPi.GPIO as GPIO

IRQtimeout=3000

def clamp(val,min,max):
  if val<min: return min
  if val>max: return max
  return val

class si4703Radio():

    # Define the register names
    SI4703_DEVICEID =       0x00
    SI4703_CHIPID =         0x01
    SI4703_POWERCFG =       0x02
    SI4703_CHANNEL =        0x03
    SI4703_SYSCONFIG1 =     0x04
    SI4703_SYSCONFIG2 =     0x05
    SI4703_SYSCONFIG3 =     0x06
    SI4703_TEST1 =          0x07
    SI4703_TEST2 =          0x08 #Reserved - if modified should be read before writing
    SI4703_BOOTCONFIG =     0x09 #Reserved - if modified should be read before writing
    SI4703_STATUSRSSI =     0x0A
    SI4703_READCHAN =       0x0B
    SI4703_RDSA =           0x0C
    SI4703_RDSB =           0x0D
    SI4703_RDSC =           0x0E
    SI4703_RDSD =           0x0F

    # Register 0x02 - POWERCFG
    SI4703_SMUTE =          15
    SI4703_DMUTE =          14
    SI4703_MONO =           13
    SI4703_RDSM =           11
    SI4703_SKMODE =         10
    SI4703_SEEKUP =         9
    SI4703_SEEK =           8
    SI4703_ENABLE =         0

    # Register 0x03 - CHANNEL
    SI4703_TUNE =           15

    # Register 0x04 - SYSCONFIG1
    SI4703_RDSIEN =         15
    SI4703_STCIEN =         14
    SI4703_RDS =            12
    SI4703_DE =             11
    SI4703_BLNDADJ =        6
    SI4703_GPIO3 =          4
    SI4703_GPIO2 =          2
    SI4703_GPIO1 =          0

    # Register 0x05 - SYSCONFIG2
    SI4703_SEEKTH =         8
    SI4703_SPACE1 =         5
    SI4703_SPACE0 =         4
    SI4703_VOLUME_MASK =    0x000F

    # Register 0x06 - SYSCONFIG3
    SI4703_RDSPRF =         9
    SI4703_SKSNR =          4
    SI4703_SKCNT =          0

    # Register 0x07 - TEST1
    SI4703_AHIZEN =         14
    SI4703_XOSCEN =         15

    # Register 0x0A - STATUSRSSI
    SI4703_RDSR =           15
    SI4703_STC =            14
    SI4703_SFBL =           13
    SI4703_AFCRL =          12
    SI4703_RDSS =           11
    SI4703_STEREO =         8

    # Register 0x0B - READCHAN
    SI4703_READCHAN_MASK =  0x03FF    

    # RDS Variables
    # Register RDSB
    SI4703_GROUPTYPE_OFFST = 11
    SI4703_TP_OFFST =       10
    SI4703_TA_OFFST =       4
    SI4703_MS_OFFST =       3
    SI4703_TYPE0_INDEX_MASK = 0x0003
    SI4703_TYPE2_INDEX_MASK = 0x000F

    SI4703_SEEK_DOWN =      0
    SI4703_SEEK_UP =        1


    def __init__(self, addr=0x10, rstpin=23, irqpin=-1, bus=1, hwreset=False, initvolume=8, hw='raspi'):
        GPIO.setwarnings(False)
        self.GPIO = GPIO

        self.i2CAddr = addr
        self.resetPin = rstpin
        self.irqPIN = irqpin
        self.initvol=clamp(initvolume,0,15)
        self.hw=hw

        #setup the GPIO variables
        self.i2c = smbus.SMBus(bus)
        if hw=='raspi':
          self.GPIO.setmode(GPIO.BCM)
          self.GPIO.setup(self.resetPin, GPIO.OUT)
          self.GPIO.setup(0, GPIO.OUT)
          self.GPIO.setwarnings(False)

        # Global shadow copy of the si4703 registers
        self.si4703_registers = [0] * 16
        self.si4703_rds_ps = [0] * 8
        self.si4703_rds_rt = [0] * 64

        if (self.irqPIN == -1): self.si4703UseIRQ = False
        else:
          self.si4703UseIRQ = True
          self.GPIO.setup(self.irqPIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        if hwreset: self.si4703hwreset(verb=True)
        #self.si4703ReadRegisters()


    # different hardware support here:

    def hwreset_raspi(self,*args,verb=True): # what hellish shenanigans are happening here? without *args was squealing about TypeError: got multiple values for argument verb
        # To get the Si4703 inito 2-wire mode, SEN needs to be high and SDIO needs to be low after a reset
        # The breakout board has SEN pulled high, but also has SDIO pulled high. Therefore, after a normal power up
        # The Si4703 will be in an unknown state. RST must be controlled
        # Configure I2C and GPIO
        self.GPIO.output(0,GPIO.LOW)
        time.sleep(0.05)
        if verb: print('hw RESET pulse (raspberry pi @'+str(self.resetPin)+'[BCM])')
        self.GPIO.output(self.resetPin, GPIO.LOW)
        time.sleep(0.1)
        self.GPIO.output(self.resetPin, GPIO.HIGH)
        time.sleep(0.05)

    def si4703hwreset(self,*args,verb=True): # what hellish shenanigans are happening here? without *args was squealing about TypeError: got multiple values for argument verb
        if   self.hw=='raspi': self.hwreset_raspi(verb=verb)
        elif self.hw=='none': pass
        #else: print('ERROR: unknown hardware specified in si4703hwreset():',hw)
        else:
          print('UNKNOWN HARDWARE:',hw)
          raise(BaseException('ERROR: unknown hardware specified in si4703hwreset()'))



    def si4703SeekUp(self,out=True):
        self.si4703Seek(1,out=out)

    def si4703SeekDown(self,out=True):
        self.si4703Seek(-1,out=out)

    def si4703Seek(self,seekDirection,out=True):
        self.si4703ReadRegisters()
        # Set seek mode wrap bit
        preg=self.si4703_registers[self.SI4703_POWERCFG] # placeholder variable to make it more readable
        preg |= (1<<self.SI4703_SKMODE) # Allow wrap
        preg &= ~(1<<self.SI4703_SEEKUP) # clear seek directin
        if(seekDirection>0): preg |= (1<<self.SI4703_SEEKUP) #Set the bit to seek up
        preg |= (1<<self.SI4703_SEEK) #Start seek
        self.si4703_registers[self.SI4703_POWERCFG]=preg
        self.si4703WriteRegisters() #Seeking will now start

        if (self.si4703UseIRQ == True):
            #self.GPIO.wait_for_edge(self.irqPIN, GPIO.FALLING, timeout=IRQtimeout)
            res=self.GPIO.wait_for_edge(self.irqPIN, GPIO.FALLING, timeout=IRQtimeout)
            if out:
              if res is None: print('[tune timeout]')
              else: print('[tuned]')
            self.si4703_registers[self.SI4703_POWERCFG] &= ~(1<<self.SI4703_SEEK)
            self.si4703WriteRegisters()
        else:
            #Poll to see if STC is set
            #while True:
            for n in range(0,40):
                time.sleep(0.05)
                self.si4703ReadRegisters()
                if( (self.si4703_registers[self.SI4703_STATUSRSSI] & (1<<self.SI4703_STC)) != 0) and out: print('[tuned]');break #tuning complete
            self.si4703ReadRegisters()
            self.si4703_registers[self.SI4703_POWERCFG] &= ~(1<<self.SI4703_SEEK) #Clear the tune after a tune has completed
            self.si4703WriteRegisters()


    def si4703SetChannel(self,channel,out=True):
        newChannel = channel * 10 # e.g. 973 * 10 = 9730
        newChannel -= 8750 # e.g. 9730 - 8750 = 980
        newChannel /= 10; # e.g. 980 / 10 = 98
        newChannel=int(newChannel)

        # These steps come from AN230 page 20 rev 0.9
        self.si4703ReadRegisters()
        self.si4703_registers[self.SI4703_CHANNEL] &= 0xFE00 # Clear out the channel bits
        self.si4703_registers[self.SI4703_CHANNEL] |= newChannel; # Mask in the new channel
#        self.si4703_registers[self.SI4703_CHANNEL] |= (1<<self.SI4703_TUNE); # Set the TUNE bit to start
        self.si4703WriteRegisters()
#        return

        if out: print('...tuning...')
        if (self.si4703UseIRQ == True):
            # loop waiting for STC bit to set
            if self.GPIO.wait_for_edge(self.irqPIN, GPIO.FALLING, timeout=IRQtimeout) is None and out: print('[tune timeout]')
            #clear the tune flag
            self.si4703_registers[self.SI4703_CHANNEL] &= ~(1<<self.SI4703_TUNE)
            self.si4703WriteRegisters()
        else:
            #Poll to see if STC is set
            #while True:
            for n in range(0,500):
                time.sleep(0.001)
                self.si4703ReadRegisters()
                if( (self.si4703_registers[self.SI4703_STATUSRSSI] & (1<<self.SI4703_STC)) != 0):
                  if out: print('tuned')
                  break #tuning complete
            self.si4703ReadRegisters()
            self.si4703_registers[self.SI4703_CHANNEL] &= ~(1<<self.SI4703_TUNE) #Clear the tune after a tune has completed
            self.si4703WriteRegisters()


    def si4703SetVolume(self,volume):
        self.si4703ReadRegisters()
        self.si4703_registers[self.SI4703_SYSCONFIG2] &= 0xFFF0 # Clear volume bits
        self.si4703_registers[self.SI4703_SYSCONFIG2] |= clamp(volume,0,15) # Set new volume
        self.si4703WriteRegisters()

    def si4703GetVolume(self):
        self.si4703ReadRegisters()
        return (self.si4703_registers[self.SI4703_SYSCONFIG2] & self.SI4703_VOLUME_MASK)

    def si4703GetChannel(self):
        self.si4703ReadRegisters()
        return ((self.si4703_registers[self.SI4703_READCHAN] & self.SI4703_READCHAN_MASK) + 875) # Mask out everything but the lower 10 bits

    def si4703ProcessRDS(self):    
        self.si4703ReadRegisters()
        if(self.si4703_registers[self.SI4703_STATUSRSSI] & (1<<self.SI4703_RDSR)):
            #read group type
            groupType = self.si4703_registers[self.SI4703_RDSB] >> self.SI4703_GROUPTYPE_OFFST

            if (groupType >> 1 == 0): #group type 0 - Program service
                ps_index = self.si4703_registers[self.SI4703_RDSB] & self.SI4703_TYPE0_INDEX_MASK

                #copy data from RDSD into the program type buffer @ index
                self.si4703_rds_ps[ps_index*2] = chr((self.si4703_registers[self.SI4703_RDSD] & 0xFF00) >> 8)
                self.si4703_rds_ps[(ps_index*2)+1] = chr((self.si4703_registers[self.SI4703_RDSD] & 0x00FF))

            elif (groupType >> 1 == 2): # group type 2 - RDS Text
                # need to add handing for 2A and 2B - only 2A for now
                rt_index = self.si4703_registers[self.SI4703_RDSB] & self.SI4703_TYPE2_INDEX_MASK

                # copy data from RDSD into the program type buffer @ index
                self.si4703_rds_rt[rt_index*4] = chr((self.si4703_registers[self.SI4703_RDSC] & 0xFF00) >> 8)
                self.si4703_rds_rt[(rt_index*4)+1] = chr((self.si4703_registers[self.SI4703_RDSC] & 0x00FF))
                self.si4703_rds_rt[(rt_index*4)+2] = chr((self.si4703_registers[self.SI4703_RDSD] & 0xFF00) >> 8)
                self.si4703_rds_rt[(rt_index*4)+3] = chr((self.si4703_registers[self.SI4703_RDSD] & 0x00FF))

            else: # more group types later
                pass

    def si4703ClearRDSBuffers(self):
        self.si4703_rds_ps[:] = []
        self.si4703_rds_rt[:] = []


    def si4703InitPwr(self):
        self.si4703ReadRegisters()
        self.si4703_registers[self.SI4703_POWERCFG] = 0x4001 # Enable the IC
        self.si4703_registers[self.SI4703_POWERCFG] |= (1<<self.SI4703_SMUTE) | (1<<self.SI4703_DMUTE) | (1<<self.SI4703_SKMODE); #//Disable Mute, disable softmute, disable seek wraparound
        self.si4703_registers[self.SI4703_POWERCFG] |= (1<<self.SI4703_RDSM) #verbose RDS
        self.si4703WriteRegisters() # Update


    def si4703isInitialized(self):
        self.si4703ReadRegisters()
        if self.si4703_registers[self.SI4703_SYSCONFIG1] & 0xff00 ==0: return False
        return True

    def si4703Init(self,verb=False):
        #print('VERB:',verb)
        self.si4703hwreset(self,verb=verb)

        self.si4703ReadRegisters()
        if verb: self.printreg(cmt='start')
#        self.si4703_registers[self.SI4703_TEST1] = 0x8100 #Enable the oscillator, from AN230 page 12, rev 0.9
        self.si4703_registers[self.SI4703_TEST1] |= 0x8100 #Enable the oscillator, from AN230 page 12, rev 0.9
#        self.si4703_registers[self.SI4703_TEST1] = 0xBC04 #Enable the oscillator, from AN230 page 12, rev 0.9
        self.si4703WriteRegisters() # Update
        if verb: self.printreg(cmt='osc_enable')
        time.sleep(0.55) # Wait for clock to settle - from AN230 page 12

##        self.si4703_registers[self.SI4703_TEST1] = 0x8100 #Enable the oscillator, from AN230 page 12, rev 0.9
##        self.si4703_registers[self.SI4703_TEST1] |= 0x8100 #Enable the oscillator, from AN230 page 12, rev 0.9
#        self.si4703_registers[self.SI4703_TEST1] = 0xBD04 #Enable the oscillator, from AN230 page 12, rev 0.9
#        self.si4703WriteRegisters() # Update
#        self.printreg(cmt='osc_enable2')
#        time.sleep(0.8) # Wait for clock to settle - from AN230 page 12

        self.si4703ReadRegisters()
        self.si4703_registers[self.SI4703_POWERCFG] = 0x4001 # Enable the IC
        self.si4703_registers[self.SI4703_POWERCFG] |= (1<<self.SI4703_SMUTE) | (1<<self.SI4703_DMUTE) | (1<<self.SI4703_SKMODE); #//Disable Mute, disable softmute, disable seek wraparound
        self.si4703_registers[self.SI4703_POWERCFG] |= (1<<self.SI4703_RDSM) #verbose RDS
        self.si4703WriteRegisters() # Update
        if verb: self.printreg(cmt='power_on')
        time.sleep(0.2) # Wait for clock to settle - from AN230 page 12

        self.si4703ReadRegisters() #Read the current register set
        self.si4703_registers[self.SI4703_SYSCONFIG1] |= (1<<self.SI4703_RDS) # Enable RDS
        self.si4703_registers[self.SI4703_SYSCONFIG1] |= (1<<self.SI4703_DE) # 50kHz Europe setup
        self.si4703_registers[self.SI4703_SYSCONFIG1] |= (3<<self.SI4703_BLNDADJ) # set stereo/mono threshold
        self.si4703_registers[self.SI4703_SYSCONFIG1] |= (1<<self.SI4703_GPIO2) # Turn GPIO2 into interrupt output
        if (self.si4703UseIRQ == True):
            #enable the si4703 IRQ pin for reading the STC flag
            self.si4703_registers[self.SI4703_SYSCONFIG1] |= (1<<self.SI4703_STCIEN) # Enable STC interrupts on GPIO2
        self.si4703_registers[self.SI4703_SYSCONFIG2] |= (0x19<<self.SI4703_SEEKTH) # setting per recommended AN230 page 40
        self.si4703_registers[self.SI4703_SYSCONFIG2] |= (1<<self.SI4703_SPACE0) # 100kHz channel spacing for *Europe!!*
        self.si4703_registers[self.SI4703_SYSCONFIG2] &= 0xFFF0 # Clear volume bits
#        self.si4703_registers[self.SI4703_SYSCONFIG2] |= 0x0001 # Set volume to lowest
        self.si4703_registers[self.SI4703_SYSCONFIG2] |= (self.initvol & 0x0f) # Set volume to lowest

#        self.si4703_registers[self.SI4703_SYSCONFIG3] |= (0x04<<self.SI4703_SKSNR) # setting per recommended AN230 page 40
#        self.si4703_registers[self.SI4703_SYSCONFIG3] |= (0x08<<self.SI4703_SKCNT) # setting per recommended AN230 page 40
        self.si4703_registers[self.SI4703_SYSCONFIG3] |= (0x01<<self.SI4703_SKSNR) # setting per recommended AN230 page 40
        self.si4703_registers[self.SI4703_SYSCONFIG3] |= (0x01<<self.SI4703_SKCNT) # setting per recommended AN230 page 40

        self.si4703_registers[self.SI4703_SYSCONFIG3] |= (0x01<<self.SI4703_RDSPRF) # high-performance RDS

        self.si4703WriteRegisters() # Update
        if verb: self.printreg(cmt='configure')
        time.sleep(.11) # Max powerup time, from datasheet page 13


    def si4703ShutDown(self, verb=True):
        self.si4703ReadRegisters() #Read the current register set
        if verb: self.printreg(cmt='power_off_start',hdr=True)
        # Powerdown as defined in AN230 page 13 rev 0.9
        self.si4703_registers[self.SI4703_TEST1] = 0x7C04 # Power down the IC
        self.si4703_registers[self.SI4703_POWERCFG] = 0x002A # Power down the IC
        self.si4703_registers[self.SI4703_SYSCONFIG1] = 0x0041 # Power down the IC
        self.si4703WriteRegisters() # Update
        if verb: self.printreg(cmt='power_off_done')


    def si4703WriteRegisters(self):
        # A write command automatically begins with register 0x02 so no need to send a write-to address
        # First we send the 0x02 to 0x07 control registers
        # In general, we should not write to registers 0x08 and 0x09

        # only need a list that holds 0x02 - 0x07: 6 words or 12 bytes
        i2cWriteBytes = [0] * 12
        #move the shadow copy into the write buffer
        for i in range(0,6):
            i2cWriteBytes[i*2], i2cWriteBytes[(i*2)+1] = divmod(self.si4703_registers[i+2], 0x100)

        # the "address" of the SMBUS write command is not used on the si4703 - need to use the first byte
        self.i2c.write_i2c_block_data(self.i2CAddr, i2cWriteBytes[0], i2cWriteBytes[1:11])


    def si4703ReadRegisters(self):
        #Read the entire register control set from 0x00 to 0x0F
        #numRegstersToRead = 16
        i2cReadBytes = [0] * 32

        #Si4703 begins reading from register upper register of 0x0A and reads to 0x0F, then loops to 0x00.
        # SMBus requires an "address" parameter even though the 4703 doesn't need one
        # Need to send the current value of the upper byte of register 0x02 as command byte
        cmdByte = self.si4703_registers[0x02] >> 8

        i2cReadBytes = self.i2c.read_i2c_block_data(self.i2CAddr, cmdByte, 32)
        regIndex = 0x0A

        #Remember, register 0x0A comes in first so we have to shuffle the array around a bit
        for i in range(0,16):
            self.si4703_registers[regIndex] = (i2cReadBytes[i*2] * 256) + i2cReadBytes[(i*2)+1]
            regIndex += 1
            if regIndex == 0x10:
                regIndex = 0
        #self.si4703printreg()


    def si4703getRssi(self):
        return self.si4703_registers[self.SI4703_STATUSRSSI]&0x0F


    def si4703printreg(self,cmt='',hdr=False):
        if hdr: self.printreghdr()
        print('REG:',':'.join(f'{i:04x}' for i in self.si4703_registers),cmt)
    def printreg(self,cmt='',hdr=False):
        self.si4703printreg(cmt=cmt,hdr=hdr)

    def printreghdr(self):
        print('REG:     chipID     chan    sysCfg2     test1    bootCfg  readChan')
        print('REG: devID    pwrCfg   sysCfg1   sysCfg3     test2    stRssi     rdsA rdsB rdsC rdsD')


    def print_version(self):
        xi=self.si4703_registers[self.SI4703_DEVICEID]
        partnostr=''
        if xi>>12 == 1: partnostr='(Si4702/Si4703)'
        x=self.si4703_registers[self.SI4703_CHIPID]
        revstr=chr(ord('@')+(x>>10))
        if revstr=='@': revstr=''
        fw=str(x&0x3f)
        dev=(x>>6)&0xf
        if dev==0: devstr='(power-off)'
        elif dev==1: devstr='Si4702'
        elif dev==9: devstr='Si4703'
        else: devstr='unknown('+str(dev)+')'
        print('VER: '+devstr+'-'+revstr+str(fw))
        print('VER:',f'dev_ID=0x{xi:04x}: part_no=0x{xi>>12:x}{partnostr} manufacturer_id=0x{xi&0xfff:03x}')
        print('VER:',f'chipID=0x{x:04x}: revision={x>>10:x} dev={dev} fw={fw}')

    def getrds(self):
        x=self.si4703_registers
        corr=[0]*4
        corr[0]=(x[self.SI4703_STATUSRSSI]>>9)&3
        corr[1]=(x[self.SI4703_READCHAN]>>14)&3
        corr[2]=(x[self.SI4703_READCHAN]>>12)&3
        corr[3]=(x[self.SI4703_READCHAN]>>10)&3
        return [x[12],x[13],x[14],x[15]],corr

    def isrds(self):
        if 0x8000 & self.si4703_registers[self.SI4703_STATUSRSSI]: return True
        return False


