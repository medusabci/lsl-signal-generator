"""
Author:   Víctor Martínez-Cagigal & Eduardo Santamaría-Vázquez
Date:     02 June 2023
Version:  2.1
"""
VERSION = "2.2"

# Images folder
IMG_FOLDER = 'gui/images'
STYLE_FILE = 'gui/style.css'

# Channels
EEG_10_20 = \
    ['C3', 'C4', 'CZ', 'F3', 'F4', 'F7', 'F8', 'FP1', 'FP2', 'FPZ', 'FZ',
     'LPA', 'NAS', 'O1', 'O2', 'OZ', 'P3', 'P4', 'P7', 'P8', 'PZ', 'RPA',
     'T7', 'T8']

EEG_10_10 = ['AF7', 'AF8', 'AFZ', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'CP1',
             'CP2', 'CP3', 'CP4', 'CP5', 'CP6', 'CPZ', 'CZ', 'F1', 'F10', 'F2',
             'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'FC1', 'FC2', 'FC3',
             'FC4', 'FC5', 'FC6', 'FCZ', 'FT10', 'FT7', 'FT8', 'FT9', 'FP1',
             'FP2', 'FPZ', 'FZ', 'I1', 'I2', 'IZ', 'LPA', 'NAS', 'NZ', 'O1',
             'O2', 'OZ', 'P1', 'P10', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7',
             'P8', 'P9', 'PO10', 'PO7', 'PO8', 'PO9', 'POZ', 'PZ', 'RPA',
             'T10', 'T7', 'T8', 'T9', 'TP7', 'TP8']

EEG_10_05 = ['AF1', 'AF10', 'AF10H', 'AF1H', 'AF2', 'AF2H', 'AF3', 'AF3H',
             'AF4', 'AF4H', 'AF5', 'AF5H', 'AF6', 'AF6H', 'AF7', 'AF7H',
             'AF8', 'AF8H', 'AF9', 'AF9H', 'AFF1', 'AFF10', 'AFF10H',
             'AFF1H', 'AFF2', 'AFF2H', 'AFF3', 'AFF3H', 'AFF4', 'AFF4H',
             'AFF5', 'AFF5H', 'AFF6', 'AFF6H', 'AFF7', 'AFF7H', 'AFF8',
             'AFF8H', 'AFF9', 'AFF9H', 'AFFZ', 'AFP1', 'AFP10', 'AFP10H',
             'AFP1H', 'AFP2', 'AFP2H', 'AFP3', 'AFP3H', 'AFP4', 'AFP4H',
             'AFP5', 'AFP5H', 'AFP6', 'AFP6H', 'AFP7', 'AFP7H', 'AFP8',
             'AFP8H', 'AFP9', 'AFP9H', 'AFPZ', 'AFZ', 'C1', 'C1H', 'C2',
             'C2H', 'C3', 'C3H', 'C4', 'C4H', 'C5', 'C5H', 'C6', 'C6H',
             'CCP1', 'CCP1H', 'CCP2', 'CCP2H', 'CCP3', 'CCP3H', 'CCP4',
             'CCP4H', 'CCP5', 'CCP5H', 'CCP6', 'CCP6H', 'CCPZ', 'CP1',
             'CP1H', 'CP2', 'CP2H', 'CP3', 'CP3H', 'CP4', 'CP4H', 'CP5',
             'CP5H', 'CP6', 'CP6H', 'CPP1', 'CPP1H', 'CPP2', 'CPP2H',
             'CPP3', 'CPP3H', 'CPP4', 'CPP4H', 'CPP5', 'CPP5H', 'CPP6',
             'CPP6H', 'CPPZ', 'CPZ', 'CZ', 'F1', 'F10', 'F10H', 'F1H', 'F2',
             'F2H', 'F3', 'F3H', 'F4', 'F4H', 'F5', 'F5H', 'F6', 'F6H', 'F7',
             'F7H', 'F8', 'F8H', 'F9', 'F9H', 'FC1', 'FC1H', 'FC2', 'FC2H',
             'FC3', 'FC3H', 'FC4', 'FC4H', 'FC5', 'FC5H', 'FC6', 'FC6H',
             'FCC1', 'FCC1H', 'FCC2', 'FCC2H', 'FCC3', 'FCC3H', 'FCC4',
             'FCC4H', 'FCC5', 'FCC5H', 'FCC6', 'FCC6H', 'FCCZ', 'FCZ', 'FFC1',
             'FFC1H', 'FFC2', 'FFC2H', 'FFC3', 'FFC3H', 'FFC4', 'FFC4H', 'FFC5',
             'FFC5H', 'FFC6', 'FFC6H', 'FFCZ', 'FFT10', 'FFT10H', 'FFT7',
             'FFT7H', 'FFT8', 'FFT8H', 'FFT9', 'FFT9H', 'FT10', 'FT10H', 'FT7',
             'FT7H', 'FT8', 'FT8H', 'FT9', 'FT9H', 'FTT10', 'FTT10H', 'FTT7',
             'FTT7H', 'FTT8', 'FTT8H', 'FTT9', 'FTT9H', 'FP1', 'FP1H', 'FP2',
             'FP2H', 'FPZ', 'FZ', 'I1', 'I1H', 'I2', 'I2H', 'IZ', 'LPA', 'N1',
             'N1H', 'N2', 'N2H', 'NAS', 'NFP1', 'NFP1H', 'NFP2', 'NFP2H',
             'NFPZ', 'NZ', 'O1', 'O1H', 'O2', 'O2H', 'OI1', 'OI1H', 'OI2',
             'OI2H', 'OIZ', 'OZ', 'P1', 'P10', 'P10H', 'P1H', 'P2', 'P2H',
             'P3', 'P3H', 'P4', 'P4H', 'P5', 'P5H', 'P6', 'P6H', 'P7', 'P7H',
             'P8', 'P8H', 'P9', 'P9H', 'PO1', 'PO10', 'PO10H', 'PO1H', 'PO2',
             'PO2H', 'PO3', 'PO3H', 'PO4', 'PO4H', 'PO5', 'PO5H', 'PO6', 'PO6H',
             'PO7', 'PO7H', 'PO8', 'PO8H', 'PO9', 'PO9H', 'POO1', 'POO10',
             'POO10H', 'POO1H', 'POO2', 'POO2H', 'POO3', 'POO3H', 'POO4',
             'POO4H', 'POO5', 'POO5H', 'POO6', 'POO6H', 'POO7', 'POO7H',
             'POO8', 'POO8H', 'POO9', 'POO9H', 'POOZ', 'POZ', 'PPO1',
             'PPO10', 'PPO10H', 'PPO1H', 'PPO2', 'PPO2H', 'PPO3', 'PPO3H',
             'PPO4', 'PPO4H', 'PPO5', 'PPO5H', 'PPO6', 'PPO6H', 'PPO7',
             'PPO7H', 'PPO8', 'PPO8H', 'PPO9', 'PPO9H', 'PPOZ', 'PZ', 'RPA',
             'T10', 'T10H', 'T7', 'T7H', 'T8', 'T8H', 'T9', 'T9H', 'TP10',
             'TP10H', 'TP7', 'TP7H', 'TP8', 'TP8H', 'TP9', 'TP9H', 'TPP10',
             'TPP10H', 'TPP7', 'TPP7H', 'TPP8', 'TPP8H', 'TPP9', 'TPP9H',
             'TTP10', 'TTP10H', 'TTP7', 'TTP7H', 'TTP8', 'TTP8H', 'TTP9',
             'TTP9H']
