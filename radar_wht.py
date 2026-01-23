#!/usr/bin/env python-sirius

import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QLabel,
                             QComboBox, QLineEdit, QFormLayout, QGroupBox, QTextEdit, QSplitter,
                             QCheckBox, QTimeEdit, QScrollArea, QFrame, QGridLayout, QHBoxLayout,)
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtGui import QMovie
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QObject
from PyQt5.QtGui import QPixmap
import epics
import threading
import pywhatkit
import datetime
import time
import subprocess

class MonitorThread(QThread, QObject):
    update_pv_log = pyqtSignal(list)
    update_pv_log_gui = pyqtSignal(list)
    signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    
    
    def __init__(self, parent=None, variaveis_epics=None, user_contacts=None):
        super(MonitorThread, self).__init__(parent)
        self.running = True
        self.variaveis_epics = variaveis_epics or self.default_variables()
        self.user_contacts = user_contacts or self.default_schedules()
        #self.schedules = MonitorThread.default_schedules(start_day=23)
        self.timer_end_msg_sent = False

    def runn(self):
        shift = epics.caget("AS-Glob:AP-MachShift:Mode-Sts")
        timer_ihm  = epics.caget('AS-Glob:PP-Summary:TunAccessWaitTimeLeft-Mon')
        timer_ihm_end = epics.caget('AS-Glob:PP-Summary:TunAccessWaitTime-Cte')
        pv_names_avar = [
            'TU-0160:AC-PT100:MeanTemperature-Mon'
            , 'TU-0308:AC-PT100:MeanTemperature-Mon', 
            'TU-0914:AC-PT100:MeanTemperature-Mon', 
            'TU-5156:AC-PT101:MeanTemperature-Mon',  
            'TU-3944:AC-PT101:MeanTemperature-Mon', 'TU-4550:AC-PT100:MeanTemperature-Mon', 
            'TU-1520:AC-PT100:MeanTemperature-Mon', 
            'TU-3338:AC-PT100:MeanTemperature-Mon',
            'TU-2126:AC-PT100:MeanTemperature-Mon', 'TU-2732:AC-PT100:MeanTemperature-Mon',
            ]
        
        average = self.get_average_pv_values(pv_names_avar)
        self.log_signal.emit(f"Média da temp. atual do túnel: {average:.2f}, Shift: {shift}")
        self.msg_tunel(average)
        self.msg_ihm(timer_ihm)
        self.msg_ihm_end(timer_ihm_end)

    def get_average_pv_values(self, pv_names_avar):
        values = []
        for pvar in pv_names_avar:
            value = epics.caget(pvar)
            if value is not None:
                values.append(value)
            else:
                print(f"Warning: Could not get value for PV: {pvar}")

        if not values:
            raise ValueError("No valid PV values retrieved.")

        average_value = sum(values) / len(values)
        average_value_rounded = round(average_value, 2)
        return average_value_rounded
    
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
            ("Corretora CC1-3 do SI-06SB:ID-VPU29 desligou (CNB)!", "SI-06SB:PS-CC1-3:PwrState-Sts", 0.5, 1.0, " Sts"),
            ("Corretora CC1-4 do SI-06SB:ID-VPU29 desligou (CNB)!", "SI-06SB:PS-CC1-4:PwrState-Sts", 0.5, 1.0, " Sts"),
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
            ("Temperatura do célula 1 da P5 fora do SP!", "BO-05D:RF-P5Cav:Cylin1T-Mon", 25.00, 31.50, " ºC"),
            ("Temperatura do célula 3 da P5 fora do SP!", "BO-05D:RF-P5Cav:Cylin3T-Mon", 25.00, 31.40, " ºC"),
            ("Temperatura do célula 5 da P5 fora do SP!", "BO-05D:RF-P5Cav:Cylin5T-Mon", 25.00, 31.30, " ºC"),
            ("Temperatura da Sala de RF fora do SP!", "RA-RaSIB02:RF-THSensor:Temp-Mon", 18.00, 28.50, " ºC"),
            ("Temperatura da Sala de RF fora do SP!", "RA-RaSIA02:RF-THSensor:Temp-Mon", 18.00, 28.50, " ºC"),
            ("Temp. da Sala de Servidores fora do SP!", "RoomSrv:CO-SIMAR-01:AmbientTemp-Mon", 15.00, 24.00, " ºC"),
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
            ("Verifique a fonte dos Quadrupolos da TB!", "TB-04:PS-QF4:PwrState-Sts", 0.5, 1.0, " Sts"),
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
            ("Verifique a temp. do Amp. H Dimtel (BbB", "SI-Glob:DI-BbBProc-H:TEMP_EXT1", 20.00, 55.00, " ºC"),
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
            # Adicione mais variáveis padrão aqui
        ]
    
    #@staticmethod
    def default_schedules(self):
        from datetime import datetime, timedelta
        today = datetime.today()
        # Encontra a última segunda-feira
        last_monday = today - timedelta(days=today.weekday())

        # Verifica se o dia da segunda-feira é ímpar ou par
        # N° finais dos contatos do GOP:
        # 7074 = Alex
        # 4332 = Carlos
        # 1530 = Vanusa
        # 5126 = Daniel
        # 9985 = Wagner
        # 8157 = Operação
        # 5222 = Walter

        if last_monday.day % 2 == 1:  # Dia ímpar
            case = 1
        else:  # Dia par
            case = 2
        if case == 1:
            return { 
                
                "+5519984217074": [{"day": "Sunday", "start": "07:00", "end": "19:00"}, {"day": "Tuesday", "start": "07:00", "end": "19:00"}, {"day": "Thursday", "start": "07:00", "end": "19:00"}, {"day": "Saturday", "start": "07:00", "end": "19:00"}],
                "+5519991844332": [{"day": "Sunday", "start": "19:00", "end": "23:59"}, {"day": "Monday", "start": "00:01", "end": "07:00"}, {"day": "Tuesday", "start": "19:00", "end": "23:59"}, {"day": "Wednesday", "start": "00:01", "end": "07:00"}, {"day": "Thursday", "start": "19:00", "end": "23:59"}, {"day": "Friday", "start": "00:01", "end": "07:00"}, {"day": "Saturday", "start": "19:00", "end": "23:59"}, {"day": "Sunday", "start": "00:01", "end": "07:00"}],
                "+5519992225126": [{"day": "Monday", "start": "19:00", "end": "23:59"}, {"day": "Tuesday", "start": "00:01", "end": "07:00"}, {"day": "Wednesday", "start": "19:00", "end": "23:59"}, {"day": "Thursday", "start": "00:00", "end": "07:00"}, {"day": "Friday", "start": "19:00", "end": "23:59"}, {"day": "Saturday", "start": "00:01", "end": "07:00"}],
                "+5519992659985": [{"day": "Monday", "start": "07:00", "end": "19:00"}, {"day": "Wednesday", "start": "07:00", "end": "19:00"}, {"day": "Friday", "start": "07:00", "end": "19:00"}],
                "+5519974231530": [{"day": "Monday", "start": "07:00", "end": "19:00"}, {"day": "Wednesday", "start": "07:00", "end": "19:00"}, {"day": "Friday", "start": "07:00", "end": "19:00"}],
                "+5519996018157": [{"day": "Monday", "start": "00:01", "end": "23:59"}, {"day": "Tuesday", "start": "00:01", "end": "23:59"}, {"day": "Wednesday", "start": "00:01", "end": "23:59"}, {"day": "Thursday", "start": "00:01", "end": "23:59"}, {"day": "Friday", "start": "00:01", "end": "23:59"}, {"day": "Saturday", "start": "00:01", "end": "23:59"}, {"day": "Sunday", "start": "00:01", "end": "23:59"}],
                "+5519997495222": [{"day": "Monday", "start": "00:01", "end": "23:59"}, {"day": "Tuesday", "start": "00:01", "end": "23:59"}, {"day": "Wednesday", "start": "00:01", "end": "23:59"}, {"day": "Thursday", "start": "00:01", "end": "23:59"}, {"day": "Friday", "start": "00:01", "end": "23:59"}, {"day": "Saturday", "start": "00:01", "end": "23:59"}, {"day": "Sunday", "start": "00:01", "end": "23:59"}],
                #"+5519992225126": [{"day": "Monday", "start": "07:00", "end": "19:00"}, {"day": "Wednesday", "start": "07:00", "end": "19:00"}, {"day": "Friday", "start": "07:00", "end": "19:00"}],
            }
        elif case == 2:
            return {
               "+5519992225126": [{"day": "Sunday", "start": "19:00", "end": "23:59"}, {"day": "Monday", "start": "00:01", "end": "07:00"}, {"day": "Tuesday", "start": "19:00", "end": "23:59"}, {"day": "Wednesday", "start": "00:01", "end": "07:00"}, {"day": "Thursday", "start": "19:00", "end": "23:59"}, {"day": "Friday", "start": "00:01", "end": "07:00"}, {"day": "Saturday", "start": "19:00", "end": "23:59"}, {"day": "Sunday", "start": "00:01", "end": "07:00"}],
               "+5519991844332": [{"day": "Monday", "start": "19:00", "end": "23:59"}, {"day": "Tuesday", "start": "00:01", "end": "07:00"}, {"day": "Wednesday", "start": "19:00", "end": "23:59"}, {"day": "Thursday", "start": "00:01", "end": "07:00"}, {"day": "Friday", "start": "19:00", "end": "23:59"}, {"day": "Saturday", "start": "00:01", "end": "07:00"}],
               "+5519984217074": [{"day": "Monday", "start": "07:00", "end": "19:00"}, {"day": "Wednesday", "start": "07:00", "end": "19:00"}, {"day": "Friday", "start": "07:00", "end": "19:00"}],
               "+5519974231530": [{"day": "Sunday", "start": "07:00", "end": "19:00"}, {"day": "Tuesday", "start": "07:00", "end": "19:00"}, {"day": "Thursday", "start": "07:00", "end": "19:00"}, {"day": "Saturday", "start": "07:00", "end": "19:00"}],
               "+5519996018157": [{"day": "Monday", "start": "00:01", "end": "23:59"}, {"day": "Tuesday", "start": "00:01", "end": "23:59"}, {"day": "Wednesday", "start": "00:01", "end": "23:59"}, {"day": "Thursday", "start": "00:01", "end": "23:59"}, {"day": "Friday", "start": "00:01", "end": "23:59"}, {"day": "Saturday", "start": "00:01", "end": "23:59"}, {"day": "Sunday", "start": "00:01", "end": "23:59"}],
               "+5519997495222": [{"day": "Monday", "start": "00:01", "end": "23:59"}, {"day": "Tuesday", "start": "00:01", "end": "23:59"}, {"day": "Wednesday", "start": "00:01", "end": "23:59"}, {"day": "Thursday", "start": "00:01", "end": "23:59"}, {"day": "Friday", "start": "00:01", "end": "23:59"}, {"day": "Saturday", "start": "00:01", "end": "23:59"}, {"day": "Sunday", "start": "00:01", "end": "23:59"}],
               "+5519992659985": [{"day": "Sunday", "start": "07:00", "end": "19:00"}, {"day": "Tuesday", "start": "07:00", "end": "19:00"}, {"day": "Thursday", "start": "07:00", "end": "19:00"}, {"day": "Saturday", "start": "07:00", "end": "19:00"}],
            }
        else:
            return "caso inválido"
        
    def msg_tunel(self, average):
        ## envio de mensagem com cálculo de PVs:
        if average < 23.90 or average > 24.10:
            for numero, schedule in self.user_contacts.items():
                current_day = datetime.datetime.now().strftime("%A")
                current_time = datetime.datetime.now().strftime("%H:%M")
                if self.is_time_within_schedule(current_day, current_time, schedule):
                    mensagem_envio = f"A média da temp. do túnel está fora do SP, valor atual: {average} ºC"
                    pywhatkit.sendwhatmsg_instantly(numero, mensagem_envio, 30, False)
                    self.signal.emit(mensagem_envio)
                    time.sleep(5)

    def msg_ihm(self, timer_ihm):
        if self.timer_end_msg_sent:
            return
        
        if timer_ihm <= 21599.9:
            for numero, schedule in self.user_contacts.items():
                current_day = datetime.datetime.now().strftime("%A")
                current_time = datetime.datetime.now().strftime("%H:%M")
                if self.is_time_within_schedule(current_day, current_time, schedule):
                    mensagem_envio = f"A contagem regressiva da IHM foi inciada, valor atual: {timer_ihm:.1f} segundos"
                    pywhatkit.sendwhatmsg_instantly(numero, mensagem_envio, 30, False)
                    self.signal.emit(mensagem_envio)
                    time.sleep(5)
                    self.timer_end_msg_sent = True
                    threading.Timer(3600, self.reset_timer_flag).start()
                    break

    def msg_ihm_end(self, timer_ihm_end):
        if self.timer_end_msg_sent:
            return
        
        if timer_ihm_end == 0:
            mensagem_envio = False
            for numero, schedule in self.user_contacts.items():
                current_day = datetime.datetime.now().strftime("%A")
                current_time = datetime.datetime.now().strftime("%H:%M")
                if self.is_time_within_schedule(current_day, current_time, schedule):
                    mensagem_envio = f"A contagem regressiva da IHM foi FINALIZADA, valor atual: {timer_ihm_end:.1f} segundos"
                    pywhatkit.sendwhatmsg_instantly(numero, mensagem_envio, 30, False)
                    self.signal.emit(mensagem_envio)
                    time.sleep(5)
                    self.timer_end_msg_sent = True
                    threading.Timer(3600, self.reset_timer_flag).start()
                    break
                time.sleep(6)

    def reset_timer_flag(self):
        self.timer_end_msg_sent = False

    def stop(self):
        self.running = False
        try:
                #self.stop_pv_monitors()
            self.terminate() 
        except Exception as e:
            self.log_signal.emit(f"Erro durante stop_pv_monitors: {e}")

    def run(self):
        schedules = self.default_schedules()
        schedules = self.user_contacts
        log_history = []
        last_alert_time = {}  
        last_alert_message = {} 
        self.update_pv_log_gui.emit([var[1] for var in self.variaveis_epics])

        while self.running:
            self.runn()
            try:
                for mensagem, variavel_epics, limite_inferior, limite_superior, grandeza, *rest in self.variaveis_epics:
                    self.log_signal.emit(f"Monitorando variável: {variavel_epics}")
                    valor = epics.caget(variavel_epics)
                    shift = epics.caget("AS-Glob:AP-MachShift:Mode-Sts")
                    lim_and = epics.caget("AS-Glob:AP-InjCtrl:Mode-Sts")
                    current_day = datetime.datetime.now().strftime("%A")
                    current_time = datetime.datetime.now().strftime("%H:%M")
                    now = datetime.datetime.now()  # Tempo atual

                    self.log_signal.emit(f"Valor atual: {valor}, Shift: {shift}")

                    if shift == 0 or shift == 4 and lim_and == 1.00:
                        if valor is not None:
                            valor_ar = round(valor, 5)
                            if valor < limite_inferior or valor > limite_superior:
                                log_entry = f"Valor fora dos limites: {valor_ar}"

                                # Verifica se o alerta é repetido no último minuto
                                last_time = last_alert_time.get(variavel_epics)
                                last_message = last_alert_message.get(variavel_epics)
                                repeated_alert = (
                                    last_message == log_entry and 
                                    last_time is not None and 
                                    (now - last_time).total_seconds() < 120  # Último alerta foi enviado no último minuto
                                )
                                
                                # Se for um alerta repetido, espera 5 minutos antes de reenviar
                                if repeated_alert:
                                    self.log_signal.emit(f"Alerta repetido detectado para {variavel_epics}. Aguardando 5 minutos para reenviar.")
                                    time.sleep(300)  # Espera 5 minutos
                                else:
                                    log_history.append(log_entry)
                                    self.log_signal.emit(log_entry)
                                    for numero, schedule in schedules.items():
                                        if self.is_time_within_schedule(current_day, current_time, schedule):
                                            if valor_ar == 0.0:
                                                mensagem_envio = f"{mensagem} PV: {variavel_epics}"
                                            else:
                                                mensagem_envio = f"{mensagem} PV: {variavel_epics}, Valor: {valor_ar:.3f} {grandeza}"
                                            try:
                                                pywhatkit.sendwhatmsg_instantly(numero, mensagem_envio, 30, False)
                                                self.signal.emit(mensagem_envio)
                                                self.log_signal.emit(f"Mensagem enviada para {numero}: {mensagem_envio}")
                                                # Atualiza o horário e a mensagem do último alerta enviado
                                                last_alert_time[variavel_epics] = now
                                                last_alert_message[variavel_epics] = log_entry
                                            except Exception as e:
                                                self.log_signal.emit(f"Erro ao enviar mensagem para {numero}: {e}")
                                            time.sleep(15)  # Pequena pausa entre os envios de mensagem
                self.check_ips(schedules, log_history)
                if len(log_history) > 100:  # Limitar o histórico de logs
                    log_history = log_history[-100:]
                #time.sleep(30)
            except Exception as e:
                self.log_signal.emit(f"Erro: {e}")
    
    def is_time_within_schedule(self, current_day, current_time, schedule):
        for s in schedule:
            if (s["day"] == current_day or s["day"] == "Everyday") and (s["start"] <= current_time <= s["end"]):
                return True
        return False

    def check_ips(self, schedules, log_history):
        ips = [
            ("10.128.1.220", "Osc. Linac e TB"), ("10.20.31.56", "LNLS210-Linux TV"), 
            ("10.0.38.77", "Osc. Eje. do Booster"), ("10.30.3.31", "Supervisório da INFRA"),
            ("10.0.38.69", "Osc. Kicker Anel"), ("10.0.38.20", "Osc. Septas Inj. Anel"), 
            ("10.128.150.78", "ICTs TS"), ("10.128.150.77", "Osc. Corr. Anel e BO"), 
            ("10.0.38.48", "Osc. Jitter Moduladores"), ("10.0.38.74", "Osc. Sep. / Kick. Inj. BO"),
        ]
        mensagem2 = "IP não está acessível! Verifique o equipamento!"

        current_day = datetime.datetime.now().strftime("%A")
        current_time = datetime.datetime.now().strftime("%H:%M")
        
        for ip, eqpt in ips:
            response = subprocess.call(['ping', '-c', '1', ip], stdout=subprocess.DEVNULL)
            if response != 0:
                log_entry = f"IP não acessível: {ip}, Equipamento: {eqpt}"
                if log_entry not in log_history:
                    log_history.append(log_entry)
                    mensagem_envio2 = f"{mensagem2} IP: {ip}, Equipamento: {eqpt}"
                    for numero, schedule in schedules.items():
                        if self.is_time_within_schedule(current_day, current_time, schedule):
                            try:
                                pywhatkit.sendwhatmsg_instantly(numero, mensagem_envio2, 30, False)
                                self.log_signal.emit(f"Mensagem enviada para {numero}: {mensagem_envio2}")
                            except Exception as e:
                                self.log_signal.emit(f"Erro ao enviar mensagem para {numero}: {e}")
                            time.sleep(15)
            else:
                log_entry = f"IP {ip}, ok"
                if log_entry not in log_history:
                    log_history.append(log_entry)
                    self.log_signal.emit(log_entry)
            if len(log_history) > 100:  # Limitar o histórico de logs
                log_history = log_history[-100:]
            time.sleep(3)



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
        self.open_label = QLabel(" LNLS - GOP ")
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
        self.use_default_combobox.addItem('Usar Configuração Padrão')
        self.use_default_combobox.addItem('Usar Configuração Personalizada')
        self.use_default_combobox.addItem('Usar Configuração Padrão + Personalizada')
        self.use_default_combobox.currentIndexChanged.connect(self.toggle_custom_variables)
    
        # Botões de variáveis personalizadas
        self.add_variable_button = QPushButton('Adicionar Variável', self)
        self.add_variable_button.clicked.connect(self.add_variable_field)
    
        self.apply_custom_vars_button = QPushButton('Aplicar Configurações Personalizadas', self)
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















