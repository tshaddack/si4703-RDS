
# area coverage (bits 9..12 of word 0, the PI)
RDS_PI_AREADESC=['local','international','national','supraregional',
                'region1','region2','region3','region4',
                'region5','region6','region7','region8',
                'region9','region10','region11','region12']

# assignment/description of groups (bits 15..11 of word 1)
RDS_GTYPE_desc={
  '0A':'basicTuning',   #TP, TA - traffic program, traffic announcement - TA in 0A,0B,15B
  '0B':'basicTuningB',  # 0B does not transmit alt freq; 0A max 25 freq
  '1A':'progItemnoSlowLabel',  # PI, extended country code/ECC; can have EW, Emergency Warning, in group var.7
  '1B':'progItemno',
  '2A':'radioText',     # 2A - max 64 bytes
  '2B':'radioTextB',    # 2B - 2x max 32 bytes, zero padded
  '3A':'openDataAppId', # ODAAID, free format
  '3B':'oda',
  '4A':'clock',
  '4B':'oda',
  '5A':'TDC/oda',       # 5A, 5B - TDC, Transparent Data Channel or ODA
  '5B':'TDC/oda',
  '6A':'inHouseA',      # 6A, 6B - IH, In-House applications (eg. remote switching) or ODA
  '6B':'inHouseB',
  '7A':'RadioPaging/oda',  # 7A - radio paging or ODA
  '7B':'oda',
  '8A':'TMC',           # 8A - TMC, Traffic Message Channel - https://tots.upol.cz/pdfs/tot/2013/01/03.pdf
  '8B':'oda',
  '9A':'EWS/oda',       # 9A - EWS, emergency warning system or ODA
  '9B':'oda',
  '10A':'progTypeName', # 10A - free format, PTYN; PTYN, ProgTYpeName, max 8 chars, zero padded
  '10B':'oda',
  '11A':'oda-freeformat',
  '11B':'oda',
  '12A':'oda-freeformat',
  '12B':'oda',
  '13A':'enhancedRadioPaging/oda',  # 13A - enhanced radio paging, or ODA free format
  '13B':'oda',
  '14A':'EON',          # 14A,14B: EON, Enhanced Other Network information, eg. traffic announcements on other stations
  '14B':'EON_B',
  '15A':'(RBDS only)',  # 15A - defined in RBDS only
  '15B':'fastBasicTuning', # 15B - fast basic tuning and switching (traffic?)
  # free format: last 5 bits of block B, and blocks C and D are 37 bits of freeform data
}


# from https://github.com/xbmc/xbmc/blob/master/xbmc/cores/VideoPlayer/VideoPlayerRadioRDS.cpp
# [0]=RDS, [1]=RBDS
RDS_RBDS_PTY_TYPES=[
  ('none', 'none'),
  ('news', 'news'),
  ('current affairs', 'information'),
  ('information', 'sport'),
  ('sport', 'talk'),
  ('education', 'rock_music'),
  ('drama', 'classic_rock_music'),
  ('culture', 'adult_hits'),
  ('science', 'soft_rock'),
  ('varied', 'top_40'),
  ('pop music', 'country'), # 10
  ('rock music', 'oldies'),
  ('mor music', 'soft'),
  ('light classical', 'nostalgia'),
  ('serious classical', 'jazz'),
  ('other music', 'classical'),
  ('weather', 'r&b'),
  ('finance', 'soft_r&b'),
  ('childrens programmes', 'language'),
  ('social affairs', 'religious_music'),
  ('religion', 'religious_talk'), # 20
  ('phone in', 'personality'),
  ('travel', 'public'),
  ('leisure', 'college'),
  ('jazz music', 'spanish talk'),
  ('country music', 'spanish music'),
  ('national music', 'hip hop'),
  ('oldies music', '?27'),
  ('folk music', '?28'),
  ('documentary', 'weather'),
  ('alarm test', 'emergency_test'),
  ('alarm', 'emergency'),
]



ODAAID_TMC=0xCD46
ODAAID_RTPLUS=0x4BD7
# names for the most common services with implemented decoders
RDS_ODAAID_names={ODAAID_TMC:'TMC',ODAAID_RTPLUS:'RT+'}

# https://www.rds.org.uk/2010/pdf/R16_026_3.pdf
# https://www.nrscstandards.org/committees/dsm/archive/rds-oda-aids.pdf
# names for more or less all known services
# x/s, x/m - standard frequency of groups per second and complete messages per minute
RDS_ODA_AID={
  # common
  0x4bd7:'RT+', # 0.2/s, 6/m; IRT RadioText+ / RT+ 2005; RadioText+ semantic tagging of 2A Radiotext #  https://tech.ebu.ch/docs/techreview/trev_307-radiotext.pdf
  0xcd46:'TMC', # 2.5/s, 12..30/m; TISA 2001; ALERT-C, EN ISO 14819 – parts 1, 2, 3 and 6 (for free-to-air or encrypted service use) where PICC = LTCC (explicitly transmitted in type 3A groups) or where a continental license agreement is registered with TISA
  0xe911:'EAS open protocol',  # 60+/m; 1998, https://www.dhs.gov/sites/default/files/publications/Accessible-Common-Alert-Protocol-Radio-Data-Sys-Demo-GulfCoastStates-508.pdf
  # less common
  0x0093:'DAB-RDS-crossref', # 2/s, 2/m, 1998, WorldDAB TC; see ETS EN 301 700
  0x0d45:'TMC ALERT-C test', # 3/s, 12..30/m; TISA 2001
  0x5757:'personalWeatherStation', # 1/s, 20/m; 2wcom 2007
  0x6365:'RDS2', # 9bit AF lists ODA; 3/s, 6/m; RDS Forum Office 2014
  0x6a7a:'WarningReceiverSweden', # 3/s, 1/m; MSB - Swedish Civil Contingencies Agency 2014 # Warning receiver (hex 6A7A) is broadcast each minute twice. # 17:07:01; 6A7A 12A 01000000 00000000
  0x7373:'Enhanced Early Warning System', # 1..2/s, 20/m; 2wcom 2007
  0xc3b0:'iTunes tagging', # NAB-assigned, 0.5/s, 8.6/m; Apple 2008; similar to RT+?
  0xcd47:'TMC arbPICC', # 2.5/s, 12..30/m; TISA 2010; ALERT-C, EN ISO 14819 – parts 1, 2, 3 and 6 (for free-to-air or encrypted service use) where PICC is arbitrary for TMC and LTCC is explicitly transmitted in type 3A groups
  # other
  0x125F:'I-FM-RDS for Fixed and Mobile devices', # Qualcomm 2008
  0x1C68:'ITIS In-vehicle database', # 1/s, 6/m; IT IS Holding PLC, 2005
  0x4400:'RDS Light', # 0.6/s, 2/m; CAMEON SA, France 2016
  0x4bd8:'RT+/eRT', # 0.2/s, 6/m; RDS Forum 2016
  0x50DD:'DisasterWarning', # 4/s, 60/m; Disaster Warning Systems Ltd 2013
  0x6552:'Enhanced RadioText / eRT', # 4/s, 6/m; RDS Forum Office 2007
  0xa112:'NL_Alert System', # open/s, open/m; Netherlands, MacBe bv 2017
  0xa911:'Data FM Selective Multipoint', # Data FM 2015
  0xC350:'NRSC Song title and artist', # NAB-assigned; 2/s, 30..60/m; NRSC 2004
  0xC4D4:'eEAS', # NAB-assigned; Alertus Technologies 2006
  0xC737:'UMC - Utility Message Channel', # NAB-assigned; e-radio 2009
  0xE123:'APS Gateway', # NAB-assigned, 1/s, 30/m; StratosAudio 2003
  0xE1C1:'eCARmerce Action code', # NAB-assigned, eCARmerce 2001
  0xE411:'Cell-Loc Beacon downlink', # NAB-assigned, Cell-Loc 2002
  0xcb73:'Citibus1', # 8/s, 4/m; TDF, 1997
  0x4c59:'Citibus2', # 8/s, 4/m; TDF, 1997
  0xcc21:'Citibus3', # 8/s, 4/m; TDF, 1997
  0x1dc2:'Citibus4', # 8/s, 4/m; TDF, 1997
  0x4aa1:'Rasant', # 1.5/s, 1/m; Freie und Hansestadt, Hamburg, Baubehörde
  0x1bda:'Electrabel-DSM1', # 3/s, 6/m; Electrabel 1999
  0x0f87:'Electrabel-DSM2', # 3/s, 6/m; Electrabel 1999
  0x0e2c:'Electrabel-DSM3', # 3/s, 6/m; Electrabel 1999
  0x1d47:'Electrabel-DSM4', # 3/s, 6/m; Electrabel 1999
  0x4ba1:'Electrabel-DSM5', # 3/s, 6/m; Electrabel 1999
  0xe5d7:'Electrabel-DSM6', # 3/s, 6/m; Electrabel 1999
  0x0c24:'Electrabel-DSM7', # 3/s, 6/m; Electrabel 1999
  0xcd9e:'Electrabel-DSM8', # 3/s, 6/m; Electrabel 1999
  0x4ab7:'Electrabel-DSM9', # 3/s, 6/m; Electrabel 1999
  0x1cb1:'Electrabel-DSM10', # 3/s, 6/m; Electrabel 1999
  0x4d9a:'Electrabel-DSM11', # 3/s, 6/m; Electrabel 1999
  0xe319:'Electrabel-DSM12', # 3/s, 6/m; Electrabel 1999
  0x0e31:'Electrabel-DSM13', # 3/s, 6/m; Electrabel 1999
  0xcb97:'Electrabel-DSM14', # 3/s, 6/m; Electrabel 1999
  0xe440:'Electrabel-DSM15', # 3/s, 6/m; Electrabel 1999
  0x4d95:'Electrabel-DSM16', # 3/s, 6/m; Electrabel 1999
  0x1e8f:'Electrabel-DSM17', # 3/s, 6/m; Electrabel 1999
  0x0d8b:'Electrabel-DSM18', # 3/s, 6/m; Electrabel 1999
  0xe4a6:'Electrabel-DSM19', # 3/s, 6/m; Electrabel 1999
  0x1c5e:'Electrabel-DSM20', # 3/s, 6/m; Electrabel 1999
  0x0bcb:'Leisure & Practical Info for Drivers', # 7/s, 10/m; TDF 1999
  0xce6b:'encrypted TTI ALERT-Plus', # 8/s, 10/m; Mediamobile SA 2001
  0x1dc5:'encrypted TTI ALERT-Plus test', # 8/s, 10/m; Mediamobile SA 2001
  0x4d87:'Radio Commerce System (RCS)', # 2/s, 2/m; CS2 AG 2001
  0x0cc1:'Wireless Playground broadcast control', # 1..3/s, 25/m; Wireless Playground B.V. 2003
  0x6363:'Hybradio RDS-Net test', # 3/s, 6/m; RDS Forum Office/Radio France 2014
  0xabcf:'RF Power Monitoring', # 1/s, 1/m; Worldcast Systems 2018
  0xff7f:'RFT Station Logo', # RDS Forum Office 2019
  0xff80:'RFT+(work)', # RDS Forum Office 2019
  0xffc0:'(RESERVEDforTESTING-a)', 
  0xffff:'(RESERVEDforTESTING-b)', 
  0xff81:'(RESERVEDforODA-RFT-a)', 
  0xffbf:'(RESERVEDforODA-RFT-b)', 
  0x4b02:'(unknown-a)', 
  0x4be4:'(unknown-b)', 
  0xe417:'(unknown-c)', 
  0xc563:'ID Logic', #NAB-assigned, 1998
  0xc360:'ALHTECH Ad-Ver', # NAB-assigned, 20/m; ALHTECH 2020
  0xc3c3:'NAVTEQ Traffic Plus', # NAB-assigned, occasional/s, 4/m; Navteq 2007
  0xc3a1:'CEA Personal Radio Service', # NAB-assigned; 9.09/s, 4/m; CEA 2009
  0xc549:'CooperPower smart grid', # NAB-assigned; Cooper Power Systems 2010
  0xc6a7:'Koplar Veil enabled interactive device', # NAB-assigned; 6/s, 10/m; Koplar Communications 2012
}


# from https://github.com/xbmc/xbmc/blob/master/xbmc/cores/VideoPlayer/VideoPlayerRadioRDS.cpp
RDSPLUS_TAGS=[
  'dummy_class',  # 0,
  'item_title',  # 1,
  'item_album',  # 2,
  'item_tracknumber',  # 3,
  'item_artist',  # 4,
  'item_composition',  # 5,
  'item_movement',  # 6,
  'item_conductor',  # 7,
  'item_composer',  # 8,
  'item_band',  # 9,
  'item_comment',  # 10,
  'item_genre',  # 11,
  'info_news',  # 12,
  'info_news_local',  # 13,
  'info_stockmarket',  # 14,
  'info_sport',  # 15,
  'info_lottery',  # 16,
  'info_horoscope',  # 17,
  'info_daily_diversion',  # 18,
  'info_health',  # 19,
  'info_event',  # 20,
  'info_szene',  # 21,
  'info_cinema',  # 22,
  'info_stupidity_machine',  # 23,
  'info_date_time',  # 24,
  'info_weather',  # 25,
  'info_traffic',  # 26,
  'info_alarm',  # 27,
  'info_advertisement',  # 28,
  'info_url',  # 29,
  'info_other',  # 30,
  'stationname_short',  # 31,
  'stationname_long',  # 32,
  'programme_now',  # 33,
  'programme_next',  # 34,
  'programme_part',  # 35,
  'programme_host',  # 36,
  'programme_editorial_staff',  # 37,
  'programme_frequency=',  # 
  'programme_homepage',  # 39,
  'programme_subchannel',  # 40,
  'phone_hotline',  # 41,
  'phone_studio',  # 42,
  'phone_other',  # 43,
  'sms_studio',  # 44,
  'sms_other',  # 45,
  'email_hotline',  # 46,
  'email_studio',  # 47,
  'email_other',  # 48,
  'mms_other',  # 49,
  'chat',  # 50,
  'chat_center',  # 51,
  'vote_question',  # 52,
  'vote_center',  # 53,
  'place',  # 59,
  'appointment',  # 60,
  'identifier',  # 61,
  'purchase',  # 62,
  'get_data',  # 63
]

