import sys

try:
    import clr
    dll_path = r"C:\Program Files\Metrohm Autolab\Autolab SDK 2.1\EcoChemie.Autolab.Sdk"
    clr.AddReference(dll_path)
    from EcoChemie.Autolab import Sdk as AutolabSDK

    instrument = AutolabSDK.Instrument()
    print("========================================")
    print("AutolabConnection properties:")
    if hasattr(instrument, "AutolabConnection"):
        conn = instrument.AutolabConnection
        for prop in dir(conn):
            if not prop.startswith("_"):
                print(f" - {prop}")
    else:
        print("No AutolabConnection attribute found!")
    print("========================================")
    
except Exception as e:
    print(f"Error: {e}")
