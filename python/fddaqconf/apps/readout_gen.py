# Set moo schema search path
from dunedaq.env import get_moo_model_path
import moo.io
moo.io.default_load_path = get_moo_model_path()

# Load configuration types
import moo.otypes

moo.otypes.load_types('flxlibs/felixcardreader.jsonnet')
moo.otypes.load_types('readoutlibs/sourceemulatorconfig.jsonnet')
moo.otypes.load_types('readoutlibs/readoutconfig.jsonnet')
moo.otypes.load_types('dfmodules/fakedataprod.jsonnet')
moo.otypes.load_types("dpdklibs/nicreader.jsonnet")


# Import new types
import dunedaq.readoutlibs.sourceemulatorconfig as sec
import dunedaq.flxlibs.felixcardreader as flxcr
import dunedaq.readoutlibs.readoutconfig as rconf
import dunedaq.dfmodules.fakedataprod as fdp
import dunedaq.dpdklibs.nicreader as nrc

# from appfwk.utils import acmd, mcmd, mrccmd, mspec
from os import path
from pathlib import Path

from daqconf.core.conf_utils import Direction, Queue
from daqconf.core.daqmodule import DAQModule
from daqconf.core.app import App, ModuleGraph
from daqconf.detreadoutmap import ReadoutUnitDescriptor, group_by_key
from daqconf.apps.readout_gen import ReadoutAppGenerator

# from detdataformats._daq_detdataformats_py import *
from detdataformats import DetID

#
# DPDK Card Reader creator
###
class NICReceiverBuilder:

    # FIXME: workaround to avoid lcore to be set to 0
    # To be reviewd
    lcore_offset = 1

    def __init__(self, rudesc : ReadoutUnitDescriptor):
        self.desc = rudesc


    def streams_by_host(self):

        iface_map = group_by_key(self.desc.streams, lambda s: s.parameters.rx_host)

        return iface_map    

    def streams_by_rxiface(self):
        """Group streams by interface

        Returns:
            dict: A map of streams with the same destination ip, mac and host
        """

        iface_map = group_by_key(self.desc.streams, lambda s: (s.parameters.rx_ip, s.parameters.rx_mac, s.parameters.rx_pcie_dev, s.parameters.rx_host))

        return iface_map

    def streams_by_rxiface_and_tx_endpoint(self):

        s_by_if = self.streams_by_rxiface()
        m = {}
        for k,v in s_by_if.items():
            m[k] = group_by_key(v, lambda s: (s.parameters.tx_ip, s.parameters.tx_mac, s.parameters.tx_host))
            
        return m

    def build_conf(self, eal_arg_list, lcores_id_set):


        streams_by_if_and_tx = self.streams_by_rxiface_and_tx_endpoint()

        ifcfgs = []
        for (rx_ip, rx_mac, rx_pcie_dev,_),txs in streams_by_if_and_tx.items():
            srcs = []
            # Sid is used for the "Source.id". What is it?

            # Transmitters are sorted by tx ip address.
            # This is not good for understanding what is what, so we sort them by minimum
            # src_id
            txs_sorted_by_src = sorted(txs.items(), key=lambda x: min(x[1], key=lambda y: y.src_id))

            for sid,((tx_ip,_,_),streams) in enumerate(txs_sorted_by_src):
                ssm = nrc.SrcStreamsMapping([
                        nrc.StreamMap(source_id=s.src_id, stream_id=s.geo_id.stream_id)
                        for s in streams
                    ])
                geo_id = streams[0].geo_id
                si = nrc.SrcGeoInfo(
                    det_id=geo_id.det_id,
                    crate_id=geo_id.crate_id,
                    slot_id=geo_id.slot_id
                )

                srcs.append(
                    nrc.Source(
                        id=sid, # FIXME what is this ID?
                        ip_addr=tx_ip,
                        lcore=lcores_id_set[sid % len(lcores_id_set)],
                        rx_q=sid,
                        src_info=si,
                        src_streams_mapping=ssm
                    )
                )
            ifcfgs.append(
                nrc.Interface(
                    ip_addr=rx_ip,
                    mac_addr=rx_mac,
                    pcie_dev_id=rx_pcie_dev,
                    expected_sources=srcs,
                    stats_reporting_cfg=nrc.StatsReporting()
                )
            )         


        conf = nrc.Conf(
            ifaces = ifcfgs,
            eal_arg_list=eal_arg_list
        )

        return conf
    

# Time to wait on pop()
QUEUE_POP_WAIT_MS = 10 # This affects stop time, as each link will wait this long before stop


class FDReadoutAppGenerator(ReadoutAppGenerator):
    dlh_plugin = "FDDataLinkHandler"

    ## Compute the frament types from detector infos
    def compute_data_types(
            self,
            stream_entry
    ):
        det_str = DetID.subdetector_to_string(DetID.Subdetector(stream_entry.geo_id.det_id))
        

        # Far detector types
        if (det_str in ("HD_TPC","VD_Bottom_TPC") and stream_entry.kind=='flx' ):
            fe_type = "wib2"
            queue_frag_type="WIB2Frame"
            fakedata_frag_type = "WIB"
            fakedata_time_tick=32
            fakedata_frame_size=472
        elif (det_str in ("HD_TPC","VD_Bottom_TPC") and stream_entry.kind=='eth' ):
            fe_type = "wibeth"
            queue_frag_type="WIBEthFrame"
            fakedata_frag_type = "WIBEth"
            fakedata_time_tick=2048
            fakedata_frame_size=7200
        elif det_str in ("HD_PDS", "VD_Cathode_PDS", "VD_Membrane_PDS") and stream_entry.parameters.mode == "var_rate":
            fe_type = "pds"
            fakedata_frag_type = "DAPHNE"
            queue_frag_type = "PDSFrame"
            fakedata_time_tick=None
            fakedata_frame_size=472
        elif det_str in ("HD_PDS", "VD_Cathode_PDS", "VD_Membrane_PDS") and  stream_entry.parameters.mode == "fix_rate":
            fe_type = "pds_stream"
            fakedata_frag_type = "DAPHNE"
            queue_frag_type = "PDSStreamFrame"
            fakedata_time_tick=None
            fakedata_frame_size=472
        elif det_str == "VD_Top_TPC":
            fe_type = "tde"
            fakedata_frag_type = "TDE_AMC"
            queue_frag_type = "TDEFrame"
            fakedata_time_tick=4472*32
            fakedata_frame_size=8972
            
        else:
            raise ValueError(f"No match for {det_str}, {stream_entry.kind}")

        return fe_type, queue_frag_type, fakedata_frag_type, fakedata_time_tick, fakedata_frame_size

    ###
    # Fake Card Reader creator
    ###
    def create_fake_cardreader(
        self,
        # FRONTEND_TYPE: str,
        # QUEUE_FRAGMENT_TYPE: str,
        DATA_FILES: dict,
        RU_DESCRIPTOR # ReadoutUnitDescriptor

    ) -> tuple[list, list]:
        """
        Create a FAKE Card reader module
        """
        cfg = self.ro_cfg

        conf = sec.Conf(
                link_confs = [
                    sec.LinkConfiguration(
                        source_id=s.src_id,
                            crate_id = s.geo_id.crate_id,
                            slot_id = s.geo_id.slot_id,
                            link_id = s.geo_id.stream_id,
                            slowdown=self.daq_cfg.data_rate_slowdown_factor,
                            queue_name=f"output_{s.src_id}",
                            data_filename = DATA_FILES[s.geo_id.det_id] if s.geo_id.det_id in DATA_FILES.keys() else cfg.default_data_file,
                            emu_frame_error_rate=0
                        ) for s in RU_DESCRIPTOR.streams],
                use_now_as_first_data_time=cfg.emulated_data_times_start_with_now,
                generate_periodic_adc_pattern = cfg.generate_periodic_adc_pattern,  
                TP_rate_per_ch = cfg.emulated_TP_rate_per_ch,  
                clock_speed_hz=self.det_cfg.clock_speed_hz,
                queue_timeout_ms = QUEUE_POP_WAIT_MS
                )


        modules = [DAQModule(name = "fake_source",
                                plugin = "FDFakeCardReader",
                                conf = conf)]
      
        queues = []
        for s in RU_DESCRIPTOR.streams:
            FRONTEND_TYPE, QUEUE_FRAGMENT_TYPE, _, _, _ = self.compute_data_types(s)
            queues.append(
                Queue(
                    f"fake_source.output_{s.src_id}",
                    f"datahandler_{s.src_id}.raw_input",
                    QUEUE_FRAGMENT_TYPE,
                    f'{FRONTEND_TYPE}_link_{s.src_id}', 100000
                )
            )

        return modules, queues


    def get_flx_card_id(self, RU_DESCRIPTOR):

        card_id = RU_DESCRIPTOR.iface
        try:
            card_id_exc = self.numa_excpt[(RU_DESCRIPTOR.host_name, RU_DESCRIPTOR.iface)]["felix_card_id"]
            if card_id_exc != -1:
                card_id = card_id_exc
        except KeyError:
            pass

        return card_id

    ###
    # FELIX Card Reader creator
    ###
    def create_felix_cardreader(
            self,
            # FRONTEND_TYPE: str,
            # QUEUE_FRAGMENT_TYPE: str,
            # CARD_ID_OVERRIDE: int,
            NUMA_ID: int,
            RU_DESCRIPTOR # ReadoutUnitDescriptor
        ) -> tuple[list, list]:
        """
        Create a FELIX Card Reader (and reader->DHL Queues?)

        [CR]->queues
        """
        links_slr0 = []
        links_slr1 = []
        strms_slr0 = []
        strms_slr1 = []
        for stream in RU_DESCRIPTOR.streams:
            if stream.parameters.slr == 0:
                links_slr0.append(stream.parameters.link)
                strms_slr0.append(stream)
            if stream.parameters.slr == 1:
                links_slr1.append(stream.parameters.link)
                strms_slr1.append(stream)

        links_slr0.sort()
        links_slr1.sort()

        # try:
        #     ex = self.numa_excpt[(RU_DESCRIPTOR.host_name, RU_DESCRIPTOR.iface)]
        #     CARD_OVERRIDE = ex['felix_card_id']
        # except KeyError:
        #     CARD_OVERRIDE = -1
        # 
        # card_id = RU_DESCRIPTOR.iface if CARD_OVERRIDE == -1 else CARD_OVERRIDE
        card_id = self.get_flx_card_id(RU_DESCRIPTOR)

        modules = []
        queues = []
        if len(links_slr0) > 0:
            modules += [DAQModule(name = 'flxcard_0',
                            plugin = 'FelixCardReader',
                            conf = flxcr.Conf(card_id = card_id,
                                                logical_unit = 0,
                                                dma_id = 0,
                                                chunk_trailer_size = 32,
                                                dma_block_size_kb = 4,
                                                dma_memory_size_gb = 4,
                                                numa_id = NUMA_ID,
                                                links_enabled = links_slr0
                                            )
                        )]
        
        if len(links_slr1) > 0:
            modules += [DAQModule(name = "flxcard_1",
                                plugin = "FelixCardReader",
                                conf = flxcr.Conf(card_id = card_id,
                                                    logical_unit = 1,
                                                    dma_id = 0,
                                                    chunk_trailer_size = 32,
                                                    dma_block_size_kb = 4,
                                                    dma_memory_size_gb = 4,
                                                    numa_id = NUMA_ID,
                                                    links_enabled = links_slr1
                                                )
                        )]
        
    
        # Queues for card reader 1
        for s in strms_slr0:
            FRONTEND_TYPE, QUEUE_FRAGMENT_TYPE, _, _, _ = self.compute_data_types(s)
            queues.append(
                Queue(
                    f'flxcard_0.output_{s.src_id}',
                    f"datahandler_{s.src_id}.raw_input",
                    QUEUE_FRAGMENT_TYPE,
                    f'{FRONTEND_TYPE}_link_{s.src_id}',
                    100000 
                )
            )
        # Queues for card reader 2
        for s in strms_slr1:
            FRONTEND_TYPE, QUEUE_FRAGMENT_TYPE, _, _, _ = self.compute_data_types(s)
            queues.append(
                Queue(
                    f'flxcard_1.output_{s.src_id}',
                    f"datahandler_{s.src_id}.raw_input",
                    QUEUE_FRAGMENT_TYPE,
                    f'{FRONTEND_TYPE}_link_{s.src_id}',
                    100000 
                )
            )


        return modules, queues


    def create_dpdk_cardreader(
            self,
            # FRONTEND_TYPE: str,
            # QUEUE_FRAGMENT_TYPE: str,
            RU_DESCRIPTOR # ReadoutUnitDescriptor
        ) -> tuple[list, list]:
        """
        Create a DPDK Card Reader (and reader->DHL Queues?)

        [CR]->queues
        """

        cfg = self.ro_cfg

        eth_ru_bldr = NICReceiverBuilder(RU_DESCRIPTOR)

        nic_reader_name = f"nic_reader_{RU_DESCRIPTOR.iface}"

        lcores_id_set = self.get_lcore_config(RU_DESCRIPTOR)

        modules = [DAQModule(
                    name=nic_reader_name,
                    plugin="NICReceiver",
                    conf=eth_ru_bldr.build_conf(
                        eal_arg_list=cfg.dpdk_eal_args,
                        lcores_id_set=lcores_id_set
                        ),
                )]
        
        queues = []
        for stream in RU_DESCRIPTOR.streams:
            FRONTEND_TYPE, QUEUE_FRAGMENT_TYPE, _, _, _ = self.compute_data_types(stream)
            queues.append(
                Queue(
                    f"{nic_reader_name}.output_{stream.src_id}",
                    f"datahandler_{stream.src_id}.raw_input",
                    QUEUE_FRAGMENT_TYPE,
                    f'{FRONTEND_TYPE}_stream_{stream.src_id}', 100000
                )
            )

        return modules, queues
    
    def create_cardreader(self, RU_DESCRIPTOR, data_file_map):
        # Create the card readers
        cr_mods = []
        cr_queues = []
        cfg = self.ro_cfg 

        # Create the card readers
        if cfg.use_fake_cards:
            fakecr_mods, fakecr_queues = self.create_fake_cardreader(
                # FRONTEND_TYPE=FRONTEND_TYPE,
                # QUEUE_FRAGMENT_TYPE=QUEUE_FRAGMENT_TYPE,
                DATA_FILES=data_file_map,
                RU_DESCRIPTOR=RU_DESCRIPTOR
            )
            cr_mods += fakecr_mods
            cr_queues += fakecr_queues
        else:
            if RU_DESCRIPTOR.kind == 'flx':
                flx_mods, flx_queues = self.create_felix_cardreader(
                    # FRONTEND_TYPE=FRONTEND_TYPE,
                    # QUEUE_FRAGMENT_TYPE=QUEUE_FRAGMENT_TYPE,
                    # CARD_ID_OVERRIDE=self.card_override,
                    NUMA_ID=self.numa_id,
                    RU_DESCRIPTOR=RU_DESCRIPTOR
                )
                cr_mods += flx_mods
                cr_queues += flx_queues

            elif RU_DESCRIPTOR.kind == 'eth' and RU_DESCRIPTOR.streams[0].parameters.protocol == "udp":
                dpdk_mods, dpdk_queues = self.create_dpdk_cardreader(
                    # FRONTEND_TYPE=FRONTEND_TYPE,
                    # QUEUE_FRAGMENT_TYPE=QUEUE_FRAGMENT_TYPE,
                    RU_DESCRIPTOR=RU_DESCRIPTOR
                )
                cr_mods += dpdk_mods
                cr_queues += dpdk_queues

        return cr_mods, cr_queues
    


    def add_volumes_resources(self, readout_app, RU_DESCRIPTOR):


        if RU_DESCRIPTOR.kind == 'flx':

            # c = card_override if card_override != -1 else RU_DESCRIPTOR.iface
            card_id = self.get_flx_card_id(RU_DESCRIPTOR)

            readout_app.resources = {
                f"felix.cern/flx{card_id}-data": "1", # requesting FLX{c}
                # "memory": f"{}Gi" # yes bro
            }

            readout_app.pod_privileged = True

            readout_app.mounted_dirs += [
                {
                    'name': 'devfs',
                    'physical_location': '/dev',
                    'in_pod_location':   '/dev',
                    'read_only': False,
                }
            ]

        # DPDK
        elif RU_DESCRIPTOR.kind == 'eth':

            readout_app.resources = {
                "intel.com/intel_sriov_dpdk": "1", # requesting sriov
                "hugepages-2Mi": "8Gi", # required  to allow hp allocation in k8s
                "memory": "96Gi" # required by k8s when hugepages are requested
            }

            readout_app.mounted_dirs += [
                {
                    'name': 'devfs',
                    'physical_location': '/dev',
                    'in_pod_location':   '/dev',
                    'read_only': False,
                },
                {
                    'name': 'linux-firmware',
                    'physical_location': '/lib/firmware',
                    'in_pod_location':   '/lib/firmware',
                    'read_only': True,
                }
            ]

            # Remove in favour of capabilites
            readout_app.pod_privileged = True
            readout_app.pod_capabilities += [
                "IPC_LOCK",
                "CAP_NET_ADMIN"
            ]
        

    
