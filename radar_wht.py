#!/usr/bin/env python-sirius

import sys
import time
import datetime
import threading
import queue
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QLabel,
    QComboBox, QLineEdit, QGroupBox, QTextEdit, QSplitter,
    QTimeEdit, QScrollArea, QFrame, QHBoxLayout, QMainWindow
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap

import epics
import pywhatkit


class AlertDispatcher(threading.Thread):
    def __init__(self, log_signal, min_repeat_interval_s=300, per_send_delay_s=2.0):
        super().__init__(daemon=True)
        self.q = queue.Queue()
        self.log_signal = log_signal
        self.running = True
        self.last_sent = {}
        self.min_repeat = float(min_repeat_interval_s)
        self.per_send_delay = float(per_send_delay_s)

    def stop(self):
        self.running = False

    def enqueue(self, numero, mensagem, pvname):
        self.q.put((numero, mensagem, pvname))

    def run(self):
        while self.running:
            try:
                numero, mensagem, pvname = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            key = (numero, pvname)
            now = time.time()
            last = self.last_sent.get(key, 0)
            if now - last < self.min_repeat:
                continue
            try:
                pywhatkit.sendwhatmsg_instantly(numero, mensagem, 30, False)
                self.log_signal.emit(f"Mensagem enviada para {numero}: {mensagem}")
                self.last_sent[key] = now
                time.sleep(self.per_send_delay)
            except Exception as e:
                self.log_signal.emit(f"Erro ao enviar mensagem para {numero}: {e}")


class MonitorThread(QThread):
    update_pv_log = pyqtSignal(list)
    update_pv_log_gui = pyqtSignal(list)
    signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self, parent=None, variaveis_epics=None, user_contacts=None,
                 ping_interval_s=600, avg_interval_s=2.0):
        super(MonitorThread, self).__init__(parent)
        self.running = True
        self.variaveis_epics = variaveis_epics or self.default_variables()
        self.user_contacts = user_contacts or self.default_schedules()
        self.timer_end_msg_sent = False
        self.last_schedule_update = datetime.date.today()

        self.dispatcher = AlertDispatcher(self.log_signal, min_repeat_interval_s=400, per_send_delay_s=2)
        self.dispatcher.start()

        self.value_cache = {}
        self.pvs = {}

        self.shift_pvname = "AS-Glob:AP-MachShift:Mode-Sts"
        self.lim_and_pvname = "AS-Glob:AP-InjCtrl:Mode-Sts"
        self.pv_names_avar = [
            'TU-0160:AC-PT100:MeanTemperature-Mon',
            'TU-0308:AC-PT100:MeanTemperature-Mon',
            'TU-0914:AC-PT100:MeanTemperature-Mon',
            'TU-5156:AC-PT101:MeanTemperature-Mon',
            'TU-3944:AC-PT101:MeanTemperature-Mon', 'TU-4550:AC-PT100:MeanTemperature-Mon',
            'TU-1520:AC-PT100:MeanTemperature-Mon',
            'TU-3338:AC-PT100:MeanTemperature-Mon',
            'TU-2126:AC-PT100:MeanTemperature-Mon', 'TU-2732:AC-PT100:MeanTemperature-Mon',
        ]
        self.ihm_left_pvname = 'AS-Glob:PP-Summary:TunAccessWaitTimeLeft-Mon'
        self.ihm_cte_pvname = 'AS-Glob:PP-Summary:TunAccessWaitTime-Cte'

        self.ping_interval_s = int(ping_interval_s)
        self.avg_interval_s = float(avg_interval_s)

        self.log_history = []
        self.ips = [
            ("10.128.1.220", "Osc. Linac e TB"), ("10.20.31.56", "LNLS210-Linux TV"),
            ("10.0.38.77", "Osc. Eje. do Booster"), ("10.30.3.31", "Supervisório da INFRA"),
            ("10.0.38.69", "Osc. Kicker Anel"), ("10.0.38.20", "Osc. Septas Inj. Anel"),
            ("10.128.150.78", "ICTs TS"), ("10.128.150.77", "Osc. Corr. Anel e BO"),
            ("10.0.38.48", "Osc. Jitter Moduladores"), ("10.0.38.74", "Osc. Sep. / Kick. Inj. BO"),
            ("10.30.18.202", "IHM Carcará"), ("10.31.18.203", "IHM Carnaúba"), ("10.31.38.213", "IHM Cateretê"),
            ("10.33.28.205", "IHM Cedro"), ("10.31.58.203", "IHM Ema"), ("10.31.28.18", "IHM Imbuia"), ("10.32.18.203", "IHM Ipê"), ("10.31.78.207", "IHM Manacá"), ("10.32.8.220", "IHM Mogno"),
            ("10.32.78.205", "IHM Paineira"), ("10.31.98.205", "IHM Sabiá"), ("10.32.68.205", "IHM Quati"),
            ("10.128.101.101", "BBB Sensor VAC"), ("10.128.102.101", "BBB Sensor VAC"), ("10.128.103.101", "BBB Sensor VAC"), ("10.128.104.101", "BBB Sensor VAC"), ("10.128.105.101", "BBB Sensor VAC"),
            ("10.128.106.101", "BBB Sensor VAC"), ("10.128.107.101", "BBB Sensor VAC"), ("10.128.108.101", "BBB Sensor VAC"), ("10.128.109.101", "BBB Sensor VAC"), ("10.128.110.101", "BBB Sensor VAC"),
            ("10.128.111.101", "BBB Sensor VAC"), ("10.128.112.101", "BBB Sensor VAC"), ("10.128.113.101", "BBB Sensor VAC"), ("10.128.114.101", "BBB Sensor VAC"), ("10.128.115.101", "BBB Sensor VAC"),
            ("10.128.116.101", "BBB Sensor VAC"), ("10.128.117.101", "BBB Sensor VAC"), ("10.128.118.101", "BBB Sensor VAC"), ("10.128.119.101", "BBB Sensor VAC"), ("10.128.120.101", "BBB Sensor VAC"),
            ("10.128.101.102", "BBB Fonte de BI"), ("10.128.101.103", "BBB Fonte de BI"), ("10.128.102.102", "BBB Fonte de BI"), ("10.128.102.103", "BBB Fonte de BI"), ("10.128.103.102", "BBB Fonte de BI"),
            ("10.128.103.103", "BBB Fonte de BI"), ("10.128.104.102", "BBB Fonte de BI"), ("10.128.105.102", "BBB Fonte de BI"), ("10.128.105.103", "BBB Fonte de BI"), ("10.128.106.102", "BBB Fonte de BI"),
            ("10.128.106.103", "BBB Fonte de BI"), ("10.128.108.102", "BBB Fonte de BI"), ("10.128.108.103", "BBB Fonte de BI"), ("10.128.109.102", "BBB Fonte de BI"), ("10.128.109.103", "BBB Fonte de BI"),
            ("10.128.110.102", "BBB Fonte de BI"), ("10.128.111.102", "BBB Fonte de BI"), ("10.128.111.103", "BBB Fonte de BI"), ("10.128.112.102", "BBB Fonte de BI"), ("10.128.113.102", "BBB Fonte de BI"),
            ("10.128.113.103", "BBB Fonte de BI"), ("10.128.114.102", "BBB Fonte de BI"), ("10.128.115.102", "BBB Fonte de BI"), ("10.128.115.103", "BBB Fonte de BI"), ("10.128.116.102", "BBB Fonte de BI"),
            ("10.128.116.103", "BBB Fonte de BI"), ("10.128.117.102", "BBB Fonte de BI"), ("10.128.117.103", "BBB Fonte de BI"), ("10.128.118.102", "BBB Fonte de BI"), ("10.128.119.102", "BBB Fonte de BI"),
            ("10.128.119.103", "BBB Fonte de BI"), ("10.128.120.102", "BBB Fonte de BI"), ("10.128.120.103", "BBB Fonte de BI"),
        ]

    @staticmethod
    def default_variables():
        return [
            ("Atenção, verefique o top up!", "SI-13C4:DI-DCCT:Current-Mon", 199.49, 201.99, " mA"),
            ("O loop do SOFB abriu!", "SI-Glob:AP-SOFB:LoopState-Sts", 0.5, 1.0, " Sts"),
            ("O loop do FOFB abriu!", "SI-Glob:AP-FOFB:LoopState-Sts", 0.5, 1.0, " Sts"),
            ("O loop do Feedfoward do Septa abriu!", "SI-01:TI-Mags-FFCorrs:State-Sts", 0.5, 1.0, " Sts"),
            ("O loop do Feedfoward do SI-14SB:ID-IVU18 abriu (PNR)!", "SI-14SB:BS-IDFF-CHCV:LoopState-Sts", 0.5, 1.0, " Sts"),
            ("O loop do Feedfoward do SI-08SB:ID-IVU18 abriu (EMA)!", "SI-08SB:BS-IDFF-CHCV:LoopState-Sts", 0.5, 1.0, " Sts"),
            ("Corretora CH-1 do SI-08SB:ID-IVU18 desligou (EMA)!", "SI-08SB:PS-CH-1:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Corretora CH-2 do SI-08SB:ID-IVU18 desligou (EMA)!", "SI-08SB:PS-CH-2:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Corretora CV-1 do SI-08SB:ID-IVU18 desligou (EMA)!", "SI-08SB:PS-CV-1:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Corretora CV-2 do SI-08SB:ID-IVU18 desligou (EMA)!", "SI-08SB:PS-CV-2:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Corretora CH-1 do SI-14SB:ID-IVU18 desligou (PNR)!", "SI-14SB:PS-CH-1:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Corretora CH-2 do SI-14SB:ID-IVU18 desligou (PNR)!", "SI-14SB:PS-CH-2:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Corretora CV-1 do SI-14SB:ID-IVU18 desligou (PNR)!", "SI-14SB:PS-CV-1:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Corretora CV-2 do SI-14SB:ID-IVU18 desligou (PNR)!", "SI-14SB:PS-CV-2:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Corretora CC1-1 do SI-06SB:ID-VPU29 desligou (CNB)!", "SI-06SB:PS-CC1-1:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Corretora CC1-2 do SI-06SB:ID-VPU29 desligou (CNB)!", "SI-06SB:PS-CC1-2:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Queda do Feixe!", "SI-Glob:AP-CurrInfo:Current-Mon", 10.99, 201.99, " mA"),
            ("Atenção, verifique as medidas do Thermo1 (SI-10-HALL43-GNT)", "RAD:Thermo1:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo2 (SI-09-RACK09-40-GNT)", "RAD:Thermo2:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo4 (SI-14-RACK14-57-GNT)", "RAD:Thermo4:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo5 (SI-19-HALL10-GNT)", "RAD:Thermo5:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo7 (SI-08-RACK08-37-GNT)", "RAD:Thermo7:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo8 (SI-01-HALL18-GT)", "RAD:Thermo8:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo9 (SI-02-HALL20-GNT)", "RAD:Thermo9:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo10 (SI-01-CHICANE01-18-GNT)", "RAD:Thermo10:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo11 (SI-20-HALL14-GNT)", "RAD:Thermo11:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo12 (SI-01-HALL16-GNT)", "RAD:Thermo12:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo13 (SI-06-HALL31-GNT)", "RAD:Thermo13:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo14 (SI-14-HALL55-GNT)", "RAD:Thermo14:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo15 (SI-12-HALL50-GNT)", "RAD:Thermo15:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do Thermo16 (SI-08-HALL38-GNT)", "RAD:Thermo16:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Atenção, verifique as medidas do BERTHOLD (SI-02-CAVITY-19-GNB)", "RAD:Berthold:TotalDoseRate:Dose", 0.1, 1.0, " uSv"),
            ("Temperatura do C4 fora do SP!", "LA-CN:H1MPS-1:K1Temp1", 18.10, 21.60, " ºC"),
            ("Temperatura do C4 fora do SP!", "LA-CN:H1MPS-1:K1Temp2", 18.10, 21.60, " ºC"),
            ("Temperatura do C4 fora do SP!", "LA-CN:H1MPS-1:K2Temp1", 18.10, 21.60, " ºC"),
            ("Temperatura do C4 fora do SP!", "LA-CN:H1MPS-1:K2Temp2", 18.10, 21.60, " ºC"),
            ("FC da Sala de Fontes desligou!", "PA-MBTemp-03:CO-PT100-Ch3:Temp-Mon", 10.00, 14.00, " °C"),
            ("Temperatura do célula 1 da P5 fora do SP!", "BO-05D:RF-P5Cav:Cylin1T-Mon", 25.00, 31.50, " ºC"),
            ("Temperatura do célula 3 da P5 fora do SP!", "BO-05D:RF-P5Cav:Cylin3T-Mon", 25.00, 31.40, " ºC"),
            ("Temperatura do célula 5 da P5 fora do SP!", "BO-05D:RF-P5Cav:Cylin5T-Mon", 25.00, 31.30, " ºC"),
            ("Temperatura da Sala de RF fora do SP!", "RA-RaSIB02:RF-THSensor:Temp-Mon", 18.00, 28.50, " ºC"),
            ("Temperatura da Sala de RF fora do SP!", "RA-RaSIA02:RF-THSensor:Temp-Mon", 18.00, 28.50, " ºC"),
            ("Temp. da Sala de Servidores fora do SP!", "RoomSrv:CO-SIMAR-01:AmbientTemp-Mon", 15.00, 24.00, " ºC"),
            ("Temp. da Sala de Conectividade fora do SP!", "CA:CO-SIMAR-01:AmbientTemp-Mon", 20.00, 25.00, " ºC"),
            ("Temp. da Sala de Fontes fora do SP!", "PA-MBTemp-01:CO-PT100-Ch3:Temp-Mon", 10.00, 18.00, " ºC"),
            ("Atenção, verifique o vácuo do Anel!", "Calc:VA-CCG-SI-Avg:Pressure-Mon", 5.0e-11, 5.0e-09, " mbar"),
            ("Atenção, verifique o vácuo do FE do Anel!", "Calc:VA-CCG-FE-Avg:Pressure-Mon", 5.0e-11, 5.0e-09, " mbar"),
            ("Atenção, verifique o vácuo da TB!", "Calc:VA-CCG-TB-Avg:Pressure-Mon", 5.0e-11, 5.0e-09, " mbar"),
            ("Atenção, verifique o vácuo da TS!", "Calc:VA-CCG-TS-Avg:Pressure-Mon", 5.0e-11, 5.0e-09, " mbar"),
            ("Atenção, verifique o vácuo do Booster!", "Calc:VA-CCG-BO-Avg:Pressure-Mon", 5.0e-11, 5.0e-09, " mbar"),
            ("Atenção, verifique o vácuo do Linac!", "LA-VA:H1VGC-01:RdPrs-1", 5.0e-11, 5.0e-09, " mbar"),
            ("Atenção, verifique o vácuo do Linac!", "LA-VA:H1VGC-01:RdPrs-2", 5.0e-11, 5.0e-09, " mbar"),
            ("Atenção, verifique o vácuo do Linac!", "LA-VA:H1VGC-02:RdPrs-1", 5.0e-11, 5.0e-09, " mbar"),
            ("Atenção, verifique o vácuo do Linac!", "LA-VA:H1VGC-02:RdPrs-2", 5.0e-11, 5.0e-09, " mbar"),
            ("Atenção, verifique o vácuo do Linac!", "LA-VA:H1VGC-03:RdPrs-1", 5.0e-11, 5.0e-09, " mbar"),
            ("O loop da Klystron 1 abriu!", "LA-CN:H1MPS-1:K1PsState_L", 0.0, 0.5, " Sts"),
            ("O loop da Klystron 2 abriu!", "LA-CN:H1MPS-1:K2PsState_L", 0.0, 0.5, " Sts"),
            ("Verifique o trigger do E-Gun!", "LA-CN:H1MPS-1:GunPermit", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Dipolos do Booster!", "BO-Fam:PS-B-1:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Dipolos do Booster!", "BO-Fam:PS-B-2:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Dipolos da TB!", "TB-Fam:PS-B:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Dipolos da TS!", "TS-Fam:PS-B:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TB-01:PS-QF1:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TB-02:PS-QF2A:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TB-02:PS-QF2B:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TB-03:PS-QF3:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TB-01:PS-QD1:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TB-02:PS-QD2A:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TB-02:PS-QD2B:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TB-03:PS-QD3:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TB-04:PS-QD4:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TS-01:PS-QF1A:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TS-01:PS-QF1B:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TS-02:PS-QF2:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TS-03:PS-QF3:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TS-03:PS-QF4:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TS-02:PS-QD2:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TS-04:PS-QD4A:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique a fonte dos Quadrupolos da TB!", "TS-04:PS-QD4B:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Verifique o Interlock de Órbita", "RA-RaSIB01:TI-EVE:Network-Mon", 0.5, 1.0, " Sts"),
            ("Verifique a temp. do Amp. V Dimtel (BbB)", "SI-Glob:DI-BbBProc-V:TEMP_EXT1", 20.00, 45.00, " ºC"),
            ("Verifique a temp. do Amp. H Dimtel (BbB", "SI-Glob:DI-BbBProc-H:TEMP_EXT1", 20.00, 45.00, " ºC"),
            ("Verifique a temp. do Amp. L Dimtel (BbB", "SI-Glob:DI-BbBProc-L:TEMP_EXT2", 20.00, 45.00, " ºC"),
            ("Verifique a potência da Klystron 2", "LA-RF:LLRF:KLY2:GET_CH1_POWER", 15.00, 21.00, " MW"),
            ("Verifique a potência da Klystron 1", "LA-RF:LLRF:KLY1:GET_CH1_POWER", 25.00, 36.00, " MW"),
            ("Rack de BPM-01 em falha", "IA-01RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-02 em falha", "IA-02RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-03 em falha", "IA-03RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-04 em falha", "IA-04RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-05 em falha", "IA-05RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-06 em falha", "IA-06RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-07 em falha", "IA-07RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-08 em falha", "IA-08RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-09 em falha", "IA-09RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-10 em falha", "IA-10RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-11 em falha", "IA-11RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-12 em falha", "IA-12RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-13 em falha", "IA-13RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-14 em falha", "IA-14RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-15 em falha", "IA-15RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-16 em falha", "IA-16RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-17 em falha", "IA-17RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-18 em falha", "IA-18RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-19 em falha", "IA-19RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
            ("Rack de BPM-20 em falha", "IA-20RaBPM:TI-AMCFPGAEVR:DevEnbl-Sts", 0.50, 1.00, " Sts"),
        ]

    def default_schedules(self):
        from datetime import datetime, timedelta
        today = datetime.today()
        delta = (7 - today.weekday()) % 7
        delta = 7 if delta == 0 else delta
        next_monday = today + timedelta(days=delta)
        case = 1 if next_monday.day % 2 == 1 else 2
        # Operadores:
        # Wagner = 9985
        # Alex = 7074
        # Carlos = 4332
        # Daniel = 5126
        # Vanusa = 1530
        # Operação = 8157
        if case == 1:
            return {
                "+5519974231530": [{"day": "Sunday", "start": "07:00", "end": "19:00"}, {"day": "Tuesday", "start": "07:00", "end": "19:00"}, {"day": "Thursday", "start": "07:00", "end": "19:00"}, {"day": "Saturday", "start": "07:00", "end": "19:00"}],
                "+5519991844332": [{"day": "Monday", "start": "19:00", "end": "23:59"}, {"day": "Tuesday", "start": "00:00", "end": "07:00"}, {"day": "Wednesday", "start": "19:00", "end": "23:59"}, {"day": "Thursday", "start": "00:00", "end": "07:00"}, {"day": "Friday", "start": "19:00", "end": "23:59"}, {"day": "Saturday", "start": "00:00", "end": "07:00"}],
                "+5519992225126": [{"day": "Monday", "start": "19:00", "end": "23:59"}, {"day": "Tuesday", "start": "00:00", "end": "07:00"}, {"day": "Wednesday", "start": "19:00", "end": "23:59"}, {"day": "Thursday", "start": "00:00", "end": "07:00"}, {"day": "Friday", "start": "19:00", "end": "23:59"}, {"day": "Saturday", "start": "00:00", "end": "07:00"}],
                "+5519992659985": [{"day": "Monday", "start": "07:00", "end": "19:00"}, {"day": "Wednesday", "start": "07:00", "end": "19:00"}, {"day": "Friday", "start": "07:00", "end": "19:00"}],
                "+5519984217074": [{"day": "Monday", "start": "19:00", "end": "23:59"}, {"day": "Tuesday", "start": "00:00", "end": "07:00"}, {"day": "Wednesday", "start": "19:00", "end": "23:59"}, {"day": "Thursday", "start": "00:00", "end": "07:00"}, {"day": "Friday", "start": "19:00", "end": "23:59"}, {"day": "Saturday", "start": "00:00", "end": "07:00"}],
                "+5519996018157": [{"day": "Monday", "start": "00:00", "end": "23:59"}, {"day": "Tuesday", "start": "00:00", "end": "23:59"}, {"day": "Wednesday", "start": "00:00", "end": "23:59"}, {"day": "Thursday", "start": "00:00", "end": "23:59"}, {"day": "Friday", "start": "00:00", "end": "23:59"}, {"day": "Saturday", "start": "00:00", "end": "23:59"}, {"day": "Sunday", "start": "00:00", "end": "23:59"}],
                #"+5519XXXX": [{"day": "Monday", "start": "00:01", "end": "23:59"}, {"day": "Tuesday", "start": "00:01", "end": "23:59"}, {"day": "Wednesday", "start": "00:01", "end": "23:59"}, {"day": "Thursday", "start": "00:01", "end": "23:59"}, {"day": "Friday", "start": "00:01", "end": "23:59"}, {"day": "Saturday", "start": "00:01", "end": "23:59"}, {"day": "Sunday", "start": "00:01", "end": "23:59"}],
                
            }
        else:
            return {
                "+5519992659985": [{"day": "Sunday", "start": "07:00", "end": "19:00"}, {"day": "Tuesday", "start": "07:00", "end": "19:00"}, {"day": "Thursday", "start": "07:00", "end": "19:00"}, {"day": "Saturday", "start": "07:00", "end": "19:00"}],
                "+5519992225126": [{"day": "Sunday", "start": "19:00", "end": "23:59"}, {"day": "Monday", "start": "00:00", "end": "07:00"}, {"day": "Tuesday", "start": "19:00", "end": "23:59"}, {"day": "Wednesday", "start": "00:00", "end": "07:00"}, {"day": "Thursday", "start": "19:00", "end": "23:59"}, {"day": "Friday", "start": "00:00", "end": "07:00"}, {"day": "Saturday", "start": "19:00", "end": "23:59"}, {"day": "Sunday", "start": "00:01", "end": "07:00"}],
                "+5519991844332": [{"day": "Sunday", "start": "19:00", "end": "23:59"}, {"day": "Monday", "start": "00:00", "end": "07:00"}, {"day": "Tuesday", "start": "19:00", "end": "23:59"}, {"day": "Wednesday", "start": "00:00", "end": "07:00"}, {"day": "Thursday", "start": "19:00", "end": "23:59"}, {"day": "Friday", "start": "00:00", "end": "07:00"}, {"day": "Saturday", "start": "19:00", "end": "23:59"}, {"day": "Sunday", "start": "00:01", "end": "07:00"}],
                "+5519974231530": [{"day": "Monday", "start": "07:00", "end": "19:00"}, {"day": "Wednesday", "start": "07:00", "end": "19:00"}, {"day": "Friday", "start": "07:00", "end": "19:00"}],
                "+5519984217074": [{"day": "Sunday", "start": "19:00", "end": "23:59"}, {"day": "Monday", "start": "00:00", "end": "07:00"}, {"day": "Tuesday", "start": "19:00", "end": "23:59"}, {"day": "Wednesday", "start": "00:00", "end": "07:00"}, {"day": "Thursday", "start": "19:00", "end": "23:59"}, {"day": "Friday", "start": "00:00", "end": "07:00"}, {"day": "Saturday", "start": "19:00", "end": "23:59"}, {"day": "Sunday", "start": "00:00", "end": "07:00"}],
                "+5519996018157": [{"day": "Monday", "start": "00:00", "end": "23:59"}, {"day": "Tuesday", "start": "00:00", "end": "23:59"}, {"day": "Wednesday", "start": "00:00", "end": "23:59"}, {"day": "Thursday", "start": "00:00", "end": "23:59"}, {"day": "Friday", "start": "00:00", "end": "23:59"}, {"day": "Saturday", "start": "00:00", "end": "23:59"}, {"day": "Sunday", "start": "00:00", "end": "23:59"}],
                #"+5519XXXX": [{"day": "Monday", "start": "00:01", "end": "23:59"}, {"day": "Tuesday", "start": "00:01", "end": "23:59"}, {"day": "Wednesday", "start": "00:01", "end": "23:59"}, {"day": "Thursday", "start": "00:01", "end": "23:59"}, {"day": "Friday", "start": "00:01", "end": "23:59"}, {"day": "Saturday", "start": "00:01", "end": "23:59"}, {"day": "Sunday", "start": "00:01", "end": "23:59"}],
            }

    def update_schedules_daily(self):
        today = datetime.date.today()
        if today != self.last_schedule_update:
            self.user_contacts = self.default_schedules()
            self.last_schedule_update = today
            self.log_signal.emit("Escalas atualizadas automaticamente.")

    def setup_pvs(self):
        def add_and_prime(pvname):
            if pvname in self.pvs:
                return
            pv = epics.PV(pvname, auto_monitor=True, connection_timeout=2.0)
            try:
                pv.wait_for_connection(timeout=2.0)
            except Exception:
                pass
            try:
                val = pv.get(timeout=0.5)
                if val is not None:
                    self.value_cache[pvname] = val
            except Exception:
                pass
            pv.add_callback(self.on_pv_change)
            self.pvs[pvname] = pv

        for _, pvname, *_ in self.variaveis_epics:
            add_and_prime(pvname)
        for aux in (self.shift_pvname, self.lim_and_pvname, self.ihm_left_pvname, self.ihm_cte_pvname):
            add_and_prime(aux)
        for pvname in self.pv_names_avar:
            add_and_prime(pvname)

        self.update_pv_log_gui.emit([var[1] for var in self.variaveis_epics])

    def on_pv_change(self, pvname=None, value=None, **kws):
        self.value_cache[pvname] = value

    def run(self):
        self.setup_pvs()
        self.log_signal.emit("MonitorThread iniciado com PVs persistentes (cache inicializado).")
        try:
            self.process_limits()
            self.process_tunnel_average()
            self.process_ihm_timers()
        except Exception as e:
            self.log_signal.emit(f"Erro na validação inicial: {e}")
        next_avg = time.time()
        next_ping = time.time()
        while self.running:
            self.update_schedules_daily()
            now = time.time()
            self.process_limits()
            if now >= next_avg:
                self.process_tunnel_average()
                self.process_ihm_timers()
                next_avg = now + self.avg_interval_s
            if now >= next_ping:
                self.check_ips_parallel()
                next_ping = now + self.ping_interval_s
            self.msleep(100)

    def process_limits(self):
        try:
            shift = self.value_cache.get(self.shift_pvname, None)
            lim_and = self.value_cache.get(self.lim_and_pvname, None)
            try:
                shift_i = int(shift) if shift is not None else None
            except Exception:
                shift_i = None
            try:
                limf = float(lim_and) if lim_and is not None else None
            except Exception:
                limf = None
            gate_ok = (shift_i == 0 and limf == 1.00) or (shift_i == 4) # and limf == 1.00)
            if not gate_ok:
                return
            current_day = datetime.datetime.now().strftime("%A")
            current_time = datetime.datetime.now().strftime("%H:%M")
            for mensagem, pvname, lo, hi, unidade, *rest in self.variaveis_epics:
                val = self.value_cache.get(pvname, None)
                if val is None:
                    continue
                try:
                    fval = float(val)
                except Exception:
                    continue
                if not (lo <= fval <= hi):
                    if fval == 0.0:
                        msg = f"{mensagem} PV: {pvname}"
                    else:
                        msg = f"{mensagem} PV: {pvname}, Valor: {fval:.3f}{unidade}"
                    recipients = self.get_destinatarios_alerta(pvname, self.user_contacts)

                    self.update_schedules_daily() # ATENÇÃO #

                    for numero, schedule in recipients.items():
                        if self.is_time_within_schedule(current_day, current_time, schedule):
                            self.dispatcher.enqueue(numero, msg, pvname)
                    time.sleep(22)
        except Exception as e:
            self.log_signal.emit(f"Erro em process_limits: {e}")

    def process_tunnel_average(self):
        values = []
        for pvname in self.pv_names_avar:
            v = self.value_cache.get(pvname, None)
            if v is not None:
                try:
                    values.append(float(v))
                except Exception:
                    pass
        if not values:
            return
        avg = round(sum(values) / len(values), 2)
        self.log_signal.emit(f"Média da temp. atual do túnel: {avg:.2f}")
        time.sleep(900)
        if avg < 23.90 or avg > 24.10:
            current_day = datetime.datetime.now().strftime("%A")
            current_time = datetime.datetime.now().strftime("%H:%M")
            mensagem_envio = f"A média da temp. do túnel está fora do SP, valor atual: {avg:.2f} ºC"
            for numero, schedule in self.user_contacts.items():
                if self.is_time_within_schedule(current_day, current_time, schedule):
                    self.dispatcher.enqueue(numero, mensagem_envio, "TUNEL_AVG")

    def process_ihm_timers(self):
        try:
            if self.timer_end_msg_sent:
                return
            left = self.value_cache.get(self.ihm_left_pvname, None)
            cte = self.value_cache.get(self.ihm_cte_pvname, None)
            if left is not None:
                try:
                    leftf = float(left)
                except Exception:
                    leftf = None
                if leftf is not None and leftf <= 21599.9:
                    current_day = datetime.datetime.now().strftime("%A")
                    current_time = datetime.datetime.now().strftime("%H:%M")
                    mensagem_envio = f"A contagem regressiva da IHM foi inciada, valor atual: {leftf:.1f} segundos"
                    for numero, schedule in self.user_contacts.items():
                        if self.is_time_within_schedule(current_day, current_time, schedule):
                            self.dispatcher.enqueue(numero, mensagem_envio, "IHM_START")
                    self.timer_end_msg_sent = True
                    threading.Timer(3600, self.reset_timer_flag).start()
                    return
            if cte is not None:
                try:
                    ctef = float(cte)
                except Exception:
                    ctef = None
                if ctef == 0:
                    current_day = datetime.datetime.now().strftime("%A")
                    current_time = datetime.datetime.now().strftime("%H:%M")
                    mensagem_envio = f"A contagem regressiva da IHM foi FINALIZADA, valor atual: {cte:.1f} segundos"
                    for numero, schedule in self.user_contacts.items():
                        if self.is_time_within_schedule(current_day, current_time, schedule):
                            self.dispatcher.enqueue(numero, mensagem_envio, "IHM_END")
                    self.timer_end_msg_sent = True
                    threading.Timer(3600, self.reset_timer_flag).start()
        except Exception as e:
            self.log_signal.emit(f"Erro em process_ihm_timers: {e}")

    def reset_timer_flag(self):
        self.timer_end_msg_sent = False

    def is_time_within_schedule(self, current_day, current_time, schedule):
        for s in schedule:
            if (s["day"] == current_day or s["day"] == "Everyday") and (s["start"] <= current_time <= s["end"]):
                return True
        return False

    def get_destinatarios_alerta(self, variavel_epics, schedules):
        rad_prefix = "RAD:"
        rad_target = "+5514996556859"
        rad_ignore_schedule = True
        is_rad = str(variavel_epics).startswith(rad_prefix)
        if is_rad:
            self.log_signal.emit(f"PV RAD detectada: {variavel_epics}")
            if rad_ignore_schedule:
                return {rad_target: [{"day": "Everyday", "start": "00:01", "end": "23:59"}]}
            else:
                if rad_target in schedules:
                    return {rad_target: schedules[rad_target]}
                else:
                    self.log_signal.emit("Número RAD não possui escala cadastrada. Alerta ignorado.")
                    return {}
        else:
            return schedules

    def check_ips_parallel(self):
        self.log_signal.emit("Iniciando verificação de IPs (paralela)...")
        def ping(ip):
            try:
                rc = subprocess.call(['ping', '-c', '1', '-W', '1', ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return ip, rc
            except Exception:
                return ip, 1
        results = []
        with ThreadPoolExecutor(max_workers=16) as ex:
            futures = [ex.submit(ping, ip) for ip, _ in self.ips]
            for f in as_completed(futures):
                results.append(f.result())
        down = {ip for ip, rc in results if rc != 0}
        current_day = datetime.datetime.now().strftime("%A")
        current_time = datetime.datetime.now().strftime("%H:%M")
        mensagem2 = "IP não está acessível! Verifique o equipamento!"
        for ip, eqpt in self.ips:
            if ip in down:
                log_entry = f"IP não acessível: {ip}, Equipamento: {eqpt}"
                if log_entry not in self.log_history:
                    self.log_history.append(log_entry)
                    mensagem_envio2 = f"{mensagem2} IP: {ip}, Equipamento: {eqpt}"
                    for numero, schedule in self.user_contacts.items():
                        if self.is_time_within_schedule(current_day, current_time, schedule):
                            self.dispatcher.enqueue(numero, mensagem_envio2, f"PING_{ip}")
            else:
                log_entry = f"IP {ip}, ok"
                if log_entry not in self.log_history:
                    self.log_history.append(log_entry)
                    self.log_signal.emit(log_entry)
        if len(self.log_history) > 100:
            self.log_history = self.log_history[-100:]

    def stop(self):
        self.running = False
        try:
            self.dispatcher.stop()
        except Exception:
            pass
        try:
            self.terminate()
        except Exception as e:
            self.log_signal.emit(f"Erro durante stop: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.monitor_thread_mirror = MonitorThread()
        self.monitor_thread = None
        self.custom_variable_list = []
        self.user_contacts = {}
        self.init_ui()
        self.custom_variables_group = QGroupBox("Variáveis Personalizadas")
        self.user_contacts_updated = pyqtSignal(dict)  # Sinal para atualizar os contatos #new
        
    def init_ui(self):
        # Configurações da Janela Principal
        self.setWindowTitle('Monitor PyWhatsapp')
        self.setGeometry(100, 100, 800, 400)
    
        # Label do logo
        self.open_label = QLabel(" LNLS - GOP                 ")
        self.open_label.setStyleSheet("font-size: 36px; font-weight: bold;")
        #self.open_label.setFixedSize(30, 50)
        self.open_label.setAlignment(Qt.AlignLeft)
        
        # Campos de texto para logs
        self.variableLogTextEdit = QTextEdit(self)
        self.variableLogTextEdit.setPlaceholderText("Logs das variáveis monitoradas...")
        self.variableLogTextEdit.setReadOnly(True)
        
        self.log_text_edit = QTextEdit(self)
        self.log_text_edit.setPlaceholderText("Logs do sistema...")
        self.log_text_edit.setReadOnly(True)
    
        # Botões de controle
        self.start_button = QPushButton('Start', self)
        self.start_button.clicked.connect(self.start_monitor)
    
        self.stop_button = QPushButton('Stop', self)
        self.stop_button.clicked.connect(self.stop_monitor)
    
        # ComboBox para escolher configuração
        self.use_default_combobox = QComboBox(self)
        self.use_default_combobox.setEnabled(False)
        self.use_default_combobox.addItem('Usar Configuração Padrão')
        self.use_default_combobox.addItem('Usar Configuração Personalizada')
        self.use_default_combobox.addItem('Usar Configuração Padrão + Personalizada')
        self.use_default_combobox.currentIndexChanged.connect(self.toggle_custom_variables)
    
        # Botões de variáveis personalizadas
        self.add_variable_button = QPushButton('Adicionar Variável', self)
        self.add_variable_button.setEnabled(False)
        self.add_variable_button.clicked.connect(self.add_variable_field)
    
        self.apply_custom_vars_button = QPushButton('Aplicar Configurações Personalizadas', self)
        self.apply_custom_vars_button.setEnabled(False)
        self.apply_custom_vars_button.clicked.connect(self.apply_custom_variables)
    
        # Configurações do Layout
        self.apply_custom_variables_layout = QVBoxLayout()
    
        # Criar widget para a área de rolagem
        self.scroll_area_widget_contents = QWidget()
        self.scroll_area_widget_contents.setLayout(self.apply_custom_variables_layout)
    
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.scroll_area_widget_contents)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
    
        # Layout principal
        main_layout = QVBoxLayout()
    
        # Layout horizontal para o logo
        h_layout = QHBoxLayout()
        pixmap = QPixmap("/home/sirius/Pictures/lnls.png")
        logo_label = QLabel(self)
        logo_label.setPixmap(pixmap)
        h_layout.addWidget(logo_label)
        h_layout.addWidget(self.open_label)
        main_layout.addLayout(h_layout)
    
        # Layout para os controles e configuração
        config_layout = QVBoxLayout()
        config_layout.addWidget(self.use_default_combobox)
        config_layout.addWidget(self.add_variable_button)
        config_layout.addWidget(self.apply_custom_vars_button)
        config_layout.addWidget(self.start_button)
        config_layout.addWidget(self.stop_button)
        config_layout.addWidget(self.scroll_area)
    
        # Layout para o status
        status_layout = QHBoxLayout()
        self.status_label = QLabel('Status: Parado', self)
        status_layout.addWidget(self.status_label)
        config_layout.addLayout(status_layout)
    
        # Layout dos logs
        logs_layout = QSplitter(Qt.Horizontal)
        logs_layout.addWidget(self.variableLogTextEdit)
        logs_layout.addWidget(self.log_text_edit)
        logs_layout.setSizes([300, 300])
    
        # Layout do grupo de contatos
        contact_group_box = QGroupBox("Gerenciar Contatos")
        contact_layout = QVBoxLayout()
        self.number_label = QLabel("Número:")
        self.number_edit = QLineEdit(self)
        self.number_edit.setPlaceholderText("Exemplo: +5511999999999")
        self.day_label = QLabel("Dia:")
        self.day_combo_box = QComboBox(self)
        self.day_combo_box.addItems(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Everyday"]
        )
        self.start_time_label = QLabel("Hora Início:")
        self.start_time_edit = QTimeEdit(self)
        self.start_time_edit.setDisplayFormat("HH:mm")
        self.end_time_label = QLabel("Hora Fim:")
        self.end_time_edit = QTimeEdit(self)
        self.end_time_edit.setDisplayFormat("HH:mm")
        self.add_contact_button = QPushButton('Adicionar Contato')
        self.add_contact_button.clicked.connect(self.add_contact)
        self.remove_contact_button = QPushButton('Remover Contato')
        self.remove_contact_button.clicked.connect(self.remove_contact)
        self.contact_list_label = QLabel("Lista de Contatos:")
        self.contact_list_combo_box = QComboBox(self)
    
        contact_layout.addWidget(self.number_label)
        contact_layout.addWidget(self.number_edit)
        contact_layout.addWidget(self.day_label)
        contact_layout.addWidget(self.day_combo_box)
        contact_layout.addWidget(self.start_time_label)
        contact_layout.addWidget(self.start_time_edit)
        contact_layout.addWidget(self.end_time_label)
        contact_layout.addWidget(self.end_time_edit)
        contact_layout.addWidget(self.add_contact_button)
        contact_layout.addWidget(self.remove_contact_button)
        contact_layout.addWidget(self.contact_list_label)
        contact_layout.addWidget(self.contact_list_combo_box)
        contact_group_box.setLayout(contact_layout)
    
        # Adicionar widgets ao layout principal
        main_layout.addLayout(config_layout)
        main_layout.addWidget(contact_group_box)
        main_layout.addWidget(logs_layout)
    
        # Configurar o widget central
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def toggle_custom_variables(self, index):
        self.custom_variables_group.setEnabled(index == 1 or index == 2)
        if index == 1 or index == 2: 
            self.start_button.setEnabled(False)
        else:
            self.start_button.setEnabled(True)

    def add_variable_field(self):
        var_layout = QVBoxLayout()
        var_fields = {}
        labels = ["Mensagem", "Variável EPICS", "Limite Inferior", "Limite Superior", "Grandeza"]
        for label in labels:
            line_edit = QLineEdit()
            var_layout.addWidget(QLabel(label))
            var_layout.addWidget(line_edit)
            var_fields[label] = line_edit

        # Add widgets directly to the layout
        self.apply_custom_variables_layout.addLayout(var_layout)

        # Create and add a QGroupBox if needed
        variable_group = QGroupBox("Variáveis Personalizadas")
        variable_group.setLayout(var_layout)
        self.apply_custom_variables_layout.addWidget(variable_group)

        self.custom_variable_list.append(var_fields)

    def apply_custom_variables(self):
        custom_vars = []
        for var_fields in self.custom_variable_list:
            mensagem = var_fields["Mensagem"].text()
            variavel = var_fields["Variável EPICS"].text()
            limite_inferior = float(var_fields["Limite Inferior"].text())
            limite_superior = float(var_fields["Limite Superior"].text())
            grandeza = var_fields["Grandeza"].text()
            custom_vars.append((mensagem, variavel, limite_inferior, limite_superior, grandeza))

        if self.use_default_combobox.currentIndex() == 2:
            custom_vars = MonitorThread.default_variables() + custom_vars
        if self.use_default_combobox.currentIndex() == 1:
            custom_vars = custom_vars

        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.wait()

        self.monitor_thread = MonitorThread(variaveis_epics=custom_vars)
        self.monitor_thread.signal.connect(self.update_status)
        self.monitor_thread.log_signal.connect(self.log_message)
        self.monitor_thread.update_pv_log.connect(self.update_pv_log)
        self.monitor_thread.update_pv_log_gui.connect(self.pv_log_gui)

        self.status_label.setText('Status: Monitorando com configuração personalizada...')
        self.log_message("Configuração personalizada aplicada. Monitorando as seguintes variáveis:")
        for var in custom_vars:
            self.log_message(f"Mensagem: {var[0]}, Variável: {var[1]}, Limite Inferior: {var[2]}, Limite Superior: {var[3]}, Grandeza: {var[4]}")
        self.monitor_thread.start()

    def start_monitor(self):
        if self.use_default_combobox.currentIndex() == 0:
            self.monitor_thread = MonitorThread()
        if self.monitor_thread and self.monitor_thread.isRunning():
            return
        self.monitor_thread = MonitorThread(variaveis_epics=self.custom_variable_list, user_contacts=self.user_contacts)
        self.monitor_thread.signal.connect(self.update_status)
        self.monitor_thread.log_signal.connect(self.log_message)
        self.monitor_thread.update_pv_log.connect(self.update_pv_log)
        self.monitor_thread.update_pv_log_gui.connect(self.pv_log_gui)
        self.status_label.setText('Status: Monitorando...')
        self.monitor_thread.start()

    def stop_monitor(self):
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.wait()
        
        self.status_label.setText('Status: Parado.')

    def update_status(self, message):
        self.status_label.setText(f'Status: {message}')

    def update_pv_log(self, pv_logs):
        for log in pv_logs:
            self.variableLogTextEdit.append(log)

    def add_contact(self, schedules):
        number = self.number_edit.text()
        day = self.day_combo_box.currentText()
        start_time = self.start_time_edit.time().toString("HH:mm")
        end_time = self.end_time_edit.time().toString("HH:mm")
        schedule = {"day": day, "start": start_time, "end": end_time} #+ schedules

        if number in self.user_contacts:
            self.user_contacts[number].append(schedule)
        else:
            self.user_contacts[number] = [schedule]
        self.contact_list_combo_box.addItem(number)
    
    def remove_contact(self):
        number = self.contact_list_combo_box.currentText()
        if number in self.user_contacts:
            del self.user_contacts[number]
            self.contact_list_combo_box.removeItem(self.contact_list_combo_box.currentIndex())

    def log_message(self, message):
        self.log_text_edit.append(message)

    def pv_log_gui(self, variable_list):
        self.variableLogTextEdit.append("Monitorando as seguintes variáveis:")
        for variable in variable_list:
            self.variableLogTextEdit.append(variable)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
