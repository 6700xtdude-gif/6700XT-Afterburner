param(
    [ValidateSet("HeadsetOnly", "Monitor")]
    [string]$Mode = "HeadsetOnly",
    [switch]$StatusOnly
)

$ErrorActionPreference = "Stop"

$Endpoints = @{
    SyncMaster     = "{0.0.0.00000000}.{3126b54e-f9d0-467a-a1a5-4728d978701e}"
    RealtekDigital = "{0.0.0.00000000}.{5de4753c-b4df-4cf7-be1a-a52b2068f23b}"
    JLabStereo     = "{0.0.0.00000000}.{ff106afc-0a41-4ca9-8c32-b1f1a9c86610}"
    JLabHandsFree  = "{0.0.0.00000000}.{c7275cef-ee54-4012-8c61-69fd006f1ad8}"
}

$CSharp = @"
using System;
using System.Runtime.InteropServices;

[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDeviceEnumerator {
    [PreserveSig] int EnumAudioEndpoints(int dataFlow, int dwStateMask, out IntPtr ppDevices);
    [PreserveSig] int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppEndpoint);
    [PreserveSig] int GetDevice([MarshalAs(UnmanagedType.LPWStr)] string pwstrId, out IMMDevice ppDevice);
    [PreserveSig] int RegisterEndpointNotificationCallback(IntPtr pClient);
    [PreserveSig] int UnregisterEndpointNotificationCallback(IntPtr pClient);
}

[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDevice {
    [PreserveSig] int Activate(ref Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
    [PreserveSig] int OpenPropertyStore(int stgmAccess, out IntPtr ppProperties);
    [PreserveSig] int GetId([MarshalAs(UnmanagedType.LPWStr)] out string ppstrId);
    [PreserveSig] int GetState(out int pdwState);
}

[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioEndpointVolume {
    [PreserveSig] int RegisterControlChangeNotify(IntPtr pNotify);
    [PreserveSig] int UnregisterControlChangeNotify(IntPtr pNotify);
    [PreserveSig] int GetChannelCount(out uint pnChannelCount);
    [PreserveSig] int SetMasterVolumeLevel(float fLevelDB, ref Guid pguidEventContext);
    [PreserveSig] int SetMasterVolumeLevelScalar(float fLevel, ref Guid pguidEventContext);
    [PreserveSig] int GetMasterVolumeLevel(out float pfLevelDB);
    [PreserveSig] int GetMasterVolumeLevelScalar(out float pfLevel);
    [PreserveSig] int SetChannelVolumeLevel(uint nChannel, float fLevelDB, ref Guid pguidEventContext);
    [PreserveSig] int SetChannelVolumeLevelScalar(uint nChannel, float fLevel, ref Guid pguidEventContext);
    [PreserveSig] int GetChannelVolumeLevel(uint nChannel, out float pfLevelDB);
    [PreserveSig] int GetChannelVolumeLevelScalar(uint nChannel, out float pfLevel);
    [PreserveSig] int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, ref Guid pguidEventContext);
    [PreserveSig] int GetMute([MarshalAs(UnmanagedType.Bool)] out bool pbMute);
}

[Guid("f8679f50-850a-41cf-9c72-430f290290c8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPolicyConfig {
    [PreserveSig] int GetMixFormat(string pszDeviceName, IntPtr ppFormat);
    [PreserveSig] int GetDeviceFormat(string pszDeviceName, bool bDefault, IntPtr ppFormat);
    [PreserveSig] int ResetDeviceFormat(string pszDeviceName);
    [PreserveSig] int SetDeviceFormat(string pszDeviceName, IntPtr pEndpointFormat, IntPtr MixFormat);
    [PreserveSig] int GetProcessingPeriod(string pszDeviceName, bool bDefault, IntPtr pmftDefaultPeriod, IntPtr pmftMinimumPeriod);
    [PreserveSig] int SetProcessingPeriod(string pszDeviceName, IntPtr pmftPeriod);
    [PreserveSig] int GetShareMode(string pszDeviceName, IntPtr pMode);
    [PreserveSig] int SetShareMode(string pszDeviceName, IntPtr mode);
    [PreserveSig] int GetPropertyValue(string pszDeviceName, bool bFxStore, IntPtr key, IntPtr pv);
    [PreserveSig] int SetPropertyValue(string pszDeviceName, bool bFxStore, IntPtr key, IntPtr pv);
    [PreserveSig] int SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string pszDeviceName, int role);
    [PreserveSig] int SetEndpointVisibility([MarshalAs(UnmanagedType.LPWStr)] string pszDeviceName, [MarshalAs(UnmanagedType.Bool)] bool bVisible);
}

public class AudioController {
    private static readonly Guid CLSID_MMDeviceEnumerator = new Guid("BCDE0395-E52F-467C-8E3D-C4579291692E");
    private static readonly Guid CLSID_PolicyConfigClient = new Guid("870af99c-171d-4f9e-af0d-e63df40c2bc9");
    private static readonly Guid IID_IAudioEndpointVolume = new Guid("5CDF2C82-841E-4546-9722-0CF74078229A");

    private static IMMDeviceEnumerator Enumerator() {
        return (IMMDeviceEnumerator)Activator.CreateInstance(Type.GetTypeFromCLSID(CLSID_MMDeviceEnumerator));
    }

    private static IPolicyConfig PolicyConfig() {
        return (IPolicyConfig)Activator.CreateInstance(Type.GetTypeFromCLSID(CLSID_PolicyConfigClient));
    }

    public static string GetDefaultId(int flow, int role) {
        IMMDevice dev;
        int hr = Enumerator().GetDefaultAudioEndpoint(flow, role, out dev);
        if (hr != 0 || dev == null) return "";
        string id;
        dev.GetId(out id);
        return id ?? "";
    }

    public static int SetDefaultAllRoles(string deviceId) {
        var pc = PolicyConfig();
        int lastHr = 0;
        for (int role = 0; role <= 2; role++) {
            int hr = pc.SetDefaultEndpoint(deviceId, role);
            if (hr != 0) lastHr = hr;
        }
        return lastHr;
    }

    public static int SetVisibility(string deviceId, bool visible) {
        return PolicyConfig().SetEndpointVisibility(deviceId, visible);
    }

    public static string SetEndpointState(string deviceId, bool muted, float scalarVolume) {
        IMMDevice dev;
        int hr = Enumerator().GetDevice(deviceId, out dev);
        if (hr != 0 || dev == null) return "GetDeviceErr:" + hr;
        object obj;
        Guid iid = IID_IAudioEndpointVolume;
        hr = dev.Activate(ref iid, 23, IntPtr.Zero, out obj);
        if (hr != 0 || obj == null) return "ActivateErr:" + hr;
        var vol = (IAudioEndpointVolume)obj;
        Guid ctx = Guid.Empty;
        int hrMute = vol.SetMute(muted, ref ctx);
        int hrVol = (scalarVolume >= 0.0f) ? vol.SetMasterVolumeLevelScalar(scalarVolume, ref ctx) : 0;
        return string.Format("MuteHR={0};VolHR={1}", hrMute, hrVol);
    }

    public static string GetEndpointStatus(string deviceId) {
        IMMDevice dev;
        int hr = Enumerator().GetDevice(deviceId, out dev);
        if (hr != 0 || dev == null) return "State=Missing;Muted=NA;Vol=NA";
        int state = 0;
        dev.GetState(out state);
        object obj;
        Guid iid = IID_IAudioEndpointVolume;
        hr = dev.Activate(ref iid, 23, IntPtr.Zero, out obj);
        if (hr != 0 || obj == null) return string.Format("State={0};Muted=NA;Vol=NA", state);
        var vol = (IAudioEndpointVolume)obj;
        bool muted = false;
        float level = -1.0f;
        vol.GetMute(out muted);
        vol.GetMasterVolumeLevelScalar(out level);
        return string.Format("State={0};Muted={1};Vol={2}", state, muted, Math.Round(level * 100));
    }
}
"@

if (-not ("AudioController" -as [type])) {
    Add-Type -TypeDefinition $CSharp
}

if (-not $StatusOnly) {
    if ($Mode -eq "HeadsetOnly") {
        $null = [AudioController]::SetEndpointState($Endpoints.SyncMaster, $true, 0.0)
        $null = [AudioController]::SetEndpointState($Endpoints.RealtekDigital, $true, 0.0)
        $visHr = [AudioController]::SetVisibility($Endpoints.SyncMaster, $false)
        $null = [AudioController]::SetVisibility($Endpoints.JLabStereo, $true)
        $null = [AudioController]::SetEndpointState($Endpoints.JLabStereo, $false, -1.0)
        $null = [AudioController]::SetEndpointState($Endpoints.JLabHandsFree, $false, -1.0)
        $defHr = [AudioController]::SetDefaultAllRoles($Endpoints.JLabStereo)
    } else {
        $visHr = [AudioController]::SetVisibility($Endpoints.SyncMaster, $true)
        $null = [AudioController]::SetEndpointState($Endpoints.SyncMaster, $false, 0.8)
        $defHr = [AudioController]::SetDefaultAllRoles($Endpoints.SyncMaster)
    }
}

[PSCustomObject]@{
    Mode               = $Mode
    DefaultConsole     = [AudioController]::GetDefaultId(0, 0)
    DefaultMultimedia  = [AudioController]::GetDefaultId(0, 1)
    DefaultComms       = [AudioController]::GetDefaultId(0, 2)
    SyncMaster         = [AudioController]::GetEndpointStatus($Endpoints.SyncMaster)
    RealtekDigital     = [AudioController]::GetEndpointStatus($Endpoints.RealtekDigital)
    JLabStereo         = [AudioController]::GetEndpointStatus($Endpoints.JLabStereo)
    JLabHandsFree      = [AudioController]::GetEndpointStatus($Endpoints.JLabHandsFree)
} | Format-List
