import sys
try:
    import clr
    dll_path = r"C:\Program Files\Metrohm Autolab\Autolab SDK 2.1\EcoChemie.Autolab.Sdk"
    clr.AddReference(dll_path)
    from EcoChemie.Autolab import Sdk as AutolabSDK

    instrument = AutolabSDK.Instrument()
    print("========================================")
    print("Connect Overloads:")
    for method in instrument.Connect.Overloads:
        print(f" - {method}")
    print("========================================")
    
except Exception as e:
    print(f"Error: {e}")
