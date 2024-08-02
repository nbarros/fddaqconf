// This is the configuration schema for fddaqconf_gen
//

local moo = import "moo.jsonnet";


local stypes = import "daqconf/types.jsonnet";
local types = moo.oschema.hier(stypes).dunedaq.daqconf.types;

local sctb = import "ctbmodules/ctbmodule.jsonnet";
local ctbmodule = moo.oschema.hier(sctb).dunedaq.ctbmodules.ctbmodule;

local scib = import "cibmodules/cibmodule.jsonnet";
local cibmodule = moo.oschema.hier(scib).dunedaq.cibmodules.cibmodule;

local sboot = import "daqconf/bootgen.jsonnet";
local bootgen = moo.oschema.hier(sboot).dunedaq.daqconf.bootgen;

local sdetector = import "daqconf/detectorgen.jsonnet";
local detectorgen = moo.oschema.hier(sdetector).dunedaq.daqconf.detectorgen;

local sdaqcommon = import "daqconf/daqcommongen.jsonnet";
local daqcommongen = moo.oschema.hier(sdaqcommon).dunedaq.daqconf.daqcommongen;

local stiming = import "daqconf/timinggen.jsonnet";
local timinggen = moo.oschema.hier(stiming).dunedaq.daqconf.timinggen;

local shsi = import "daqconf/hsigen.jsonnet";
local hsigen = moo.oschema.hier(shsi).dunedaq.daqconf.hsigen;

local sreadout = import "fddaqconf/readoutgen.jsonnet";
local readoutgen = moo.oschema.hier(sreadout).dunedaq.fddaqconf.readoutgen;

local strigger = import "daqconf/triggergen.jsonnet";
local triggergen = moo.oschema.hier(strigger).dunedaq.daqconf.triggergen;

local sdataflow = import "daqconf/dataflowgen.jsonnet";
local dataflowgen = moo.oschema.hier(sdataflow).dunedaq.daqconf.dataflowgen;

local s = moo.oschema.schema("dunedaq.fddaqconf.confgen");
local nc = moo.oschema.numeric_constraints;
// A temporary schema construction context.

local cs = {
  // port:            s.number(   "Port", "i4", doc="A TCP/IP port number"),
  // freq:            s.number(   "Frequency", "u4", doc="A frequency"),
  // rate:            s.number(   "Rate", "f8", doc="A rate as a double"),
  // count:           s.number(   "count", "i8", doc="A count of things"),
  // three_choice:    s.number(   "threechoice", "i8", nc(minimum=0, exclusiveMaximum=3), doc="A choice between 0, 1, or 2"),
  // flag:            s.boolean(  "Flag", doc="Parameter that can be used to enable or disable functionality"),
  // monitoring_dest: s.enum(     "MonitoringDest", ["local", "cern", "pocket"]),
  // path:            s.string(   "Path", doc="Location on a filesystem"),
  // paths:           s.sequence( "Paths",         self.path, doc="Multiple paths"),
  // host:            s.string(   "Host",          moo.re.dnshost, doc="A hostname"),
  // hosts:           s.sequence( "Hosts",         self.host, "Multiple hosts"),
  // string:          s.string(   "Str",           doc="Generic string"),
  // strings:         s.sequence( "Strings",  self.string, doc="List of strings"),

  // tpg_channel_map: s.enum(     "TPGChannelMap", ["VDColdboxChannelMap", "ProtoDUNESP1ChannelMap", "PD2HDChannelMap", "HDColdboxChannelMap"]),
  // tc_types:        s.sequence( "TCTypes",       self.count, doc="List of TC types"),
  // tc_type:         s.number(   "TCType",        "i4", nc(minimum=0, maximum=9), doc="Number representing TC type. Currently ranging from 0 to 9"),
  // tc_interval:     s.number(   "TCInterval",    "i8", nc(minimum=1, maximum=30000000000), doc="The intervals between TCs that are inserted into MLT by CTCM, in clock ticks"),
  // tc_intervals:    s.sequence( "TCIntervals",   self.tc_interval, doc="List of TC intervals used by CTCM"),
  // readout_time:    s.number(   "ROTime",        "i8", doc="A readout time in ticks"),
  // channel_list:    s.sequence( "ChannelList",   self.count, doc="List of offline channels to be masked out from the TPHandler"),
  // tpg_algo_choice: s.enum(     "TPGAlgoChoice", ["SimpleThreshold", "AbsRS"], doc="Trigger algorithm choice"),
  // pm_choice:       s.enum(     "PMChoice", ["k8s", "ssh"], doc="Process Manager choice: ssh or Kubernetes"),
  // rte_choice:      s.enum(     "RTEChoice", ["auto", "release", "devarea"], doc="Kubernetes DAQ application RTE choice"),
  

  ctb_hsi: s.record("ctb_hsi", [
    # ctb options
    s.field( "use_ctb_hsi", types.flag, default=false, doc='Flag to control whether CTB HSI config is generated. Default is false'),
    s.field( "host_ctb_hsi", types.host, default='localhost', doc='Host to run the HSI app on'),
    s.field( "hlt_triggers", ctbmodule.Hlt_trigger_seq, []),
    s.field( "beam_llt_triggers", ctbmodule.Llt_mask_trigger_seq, []),
    s.field( "crt_llt_triggers", ctbmodule.Llt_count_trigger_seq, []),
    s.field( "pds_llt_triggers", ctbmodule.Llt_count_trigger_seq, []),
    s.field( "fake_trig_1", ctbmodule.Randomtrigger, ctbmodule.Randomtrigger),
    s.field( "fake_trig_2", ctbmodule.Randomtrigger, ctbmodule.Randomtrigger)
  ]),


  cib_hsi_inst: s.record("cib_hsi_inst",[
  	s.field("trigger"	,types.int4, default=25, nc(minimum=25, exclusiveMaximum=29), doc='Which CIB trigger is mapped by this instance'),
  	s.field("host" 	 	,types.host, default='localhost',			doc='Host where this HSI app instance will run'),
  	s.field("cib_host"	,types.host, default="np04-iols-cib-01", 	doc='CIB endpoint host'),
  	s.field("cib_port"	,types.port, default=8992, 					doc='CIB endpoint port'),  	
  ]),
  
  // the number of entries on this sequence should match the number of instances for the laser system
  cib_seq : s.sequence("cib_hsi_instances",	self.cib_hsi_inst, doc="list of CIB HSI instances"),
  
  cib_hsi: s.record("cib_hsi", [
    # cib module options
    s.field( "use_cib_hsi", 	types.flag, default=false, doc='Flag to control whether CIB HSI config is generated. Default is false'),	
    s.field( "cib_num_modules", types.int4, default=1, doc='Number of modules to be instantiated. Default is 2 (one per periscope)'),
	s.field( "cib_instances",	self.cib_seq , default=[self.cib_hsi_inst], doc="List of configurations for each instance"),
  ]),


  fddaqconf_gen: s.record('fddaqconf_gen', [
    s.field('detector',    detectorgen.detector,   default=detectorgen.detector,     doc='Boot parameters'),
    s.field('daq_common',  daqcommongen.daq_common, default=daqcommongen.daq_common,   doc='DAQ common parameters'),
    s.field('boot',        bootgen.boot,    default=bootgen.boot,      doc='Boot parameters'),
    s.field('dataflow',    dataflowgen.dataflow,   default=dataflowgen.dataflow,     doc='Dataflow paramaters'),
    s.field('hsi',         hsigen.hsi,        default=hsigen.hsi,          doc='HSI parameters'),
    s.field('ctb_hsi',     self.ctb_hsi,    default=self.ctb_hsi,      doc='CTB parameters'),
    s.field('cib_hsi',     self.cib_hsi,    default=self.cib_hsi,      doc='CIB parameters'),
    s.field('readout',     readoutgen.readout,    default=readoutgen.readout,      doc='Readout parameters'),
    s.field('timing',      timinggen.timing,     default=timinggen.timing,       doc='Timing parameters'),
    s.field('trigger',     triggergen.trigger,    default=triggergen.trigger,      doc='Trigger parameters')
  ]),

};

// Output a topologically sorted array.
stypes + sboot + sdetector + sdaqcommon + stiming + shsi + sreadout + strigger + sdataflow + sctb + scib + moo.oschema.sort_select(cs)
