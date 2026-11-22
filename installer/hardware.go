package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
)

// ToolCheck describes the presence and path of an external tool.
type ToolCheck struct {
	Name  string
	Found bool
	Path  string
}

// SystemReport captures hardware, GPU driver, policy, and tool state.
type SystemReport struct {
	OS              string
	Arch            string
	Hostname        string
	GPUs            []string
	HasRX6700XT     bool
	CPUs            []string
	TotalRAMGiB     float64
	VulkanOK        bool
	VulkanNote      string
	ROCmNote        string
	SmartAppControl string
	ExecPolicy      string
	Tools           []ToolCheck
	LlamaBinaryPath string
}

// IsRX6700XTID returns true if a PCI device string or vendor/device pair matches AMD RX 6700 XT (1002:73DF).
func IsRX6700XTID(text string) bool {
	u := strings.ToUpper(text)
	if strings.Contains(u, "6700 XT") {
		return true
	}
	return strings.Contains(u, "1002") && strings.Contains(u, "73DF")
}

// ParseLinuxPCIDevice checks sysfs vendor/device hex strings (e.g. "0x1002", "0x73df").
func ParseLinuxPCIDevice(vendor, device string) bool {
	v := strings.TrimPrefix(strings.ToLower(strings.TrimSpace(vendor)), "0x")
	d := strings.TrimPrefix(strings.ToLower(strings.TrimSpace(device)), "0x")
	return v == "1002" && d == "73df"
}

// DetectSystem inspects the host OS, GPUs, drivers, policies, and AI stack tools.
func DetectSystem(installDir string) SystemReport {
	host, _ := os.Hostname()
	rep := SystemReport{
		OS:       runtime.GOOS,
		Arch:     runtime.GOARCH,
		Hostname: host,
	}

	if runtime.GOOS == "windows" {
		detectWindows(&rep, installDir)
	} else {
		detectLinux(&rep, installDir)
	}

	return rep
}

type winSysJSON struct {
	GPUs []struct {
		Name       string `json:"Name"`
		PNP        string `json:"PNPDeviceID"`
		DriverVer  string `json:"DriverVersion"`
		Status     string `json:"Status"`
		AdapterRAM uint64 `json:"AdapterRAM"`
	} `json:"GPUs"`
	CPUs []struct {
		Name    string `json:"Name"`
		Cores   int    `json:"NumberOfCores"`
		Threads int    `json:"NumberOfLogicalProcessors"`
	} `json:"CPUs"`
	RAMBytes uint64 `json:"RAMBytes"`
	SAC      *int   `json:"SAC"`
	EP       string `json:"EP"`
}

func detectWindows(rep *SystemReport, installDir string) {
	psScript := `$ErrorActionPreference = 'SilentlyContinue'
$gpus = @(Get-CimInstance Win32_VideoController | Select-Object Name, PNPDeviceID, DriverVersion, Status, AdapterRAM)
$cpus = @(Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors)
$cs = Get-CimInstance Win32_ComputerSystem
$sacProp = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' -Name 'VerifiedAndReputablePolicyState'
$map = @{}
foreach ($r in (Get-ExecutionPolicy -List)) { $map[$r.Scope.ToString()] = $r.ExecutionPolicy.ToString() }
$ep = 'Restricted'
foreach ($sc in @('MachinePolicy','UserPolicy','CurrentUser','LocalMachine')) {
    if ($map[$sc] -and $map[$sc] -ne 'Undefined') { $ep = $map[$sc]; break }
}
[PSCustomObject]@{
    GPUs = $gpus
    CPUs = $cpus
    RAMBytes = [uint64]$cs.TotalPhysicalMemory
    SAC = if ($null -ne $sacProp) { [int]$sacProp.VerifiedAndReputablePolicyState } else { $null }
    EP = $ep
} | ConvertTo-Json -Depth 4 -Compress`

	out, err := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", psScript).Output()
	if err == nil {
		var parsed winSysJSON
		if jsonErr := json.Unmarshal(bytes.TrimSpace(out), &parsed); jsonErr == nil {
			for _, g := range parsed.GPUs {
				label := fmt.Sprintf("%s (Driver %s, Status %s)", strings.TrimSpace(g.Name), g.DriverVer, g.Status)
				if IsRX6700XTID(g.Name + " " + g.PNP) {
					rep.HasRX6700XT = true
					label += " [Navi 22 / gfx1031]"
				}
				rep.GPUs = append(rep.GPUs, label)
			}
			for _, c := range parsed.CPUs {
				rep.CPUs = append(rep.CPUs, fmt.Sprintf("%s (%dC/%dT)", strings.TrimSpace(c.Name), c.Cores, c.Threads))
			}
			if parsed.RAMBytes > 0 {
				rep.TotalRAMGiB = float64(parsed.RAMBytes) / (1024 * 1024 * 1024)
			}
			if parsed.SAC != nil {
				if *parsed.SAC == 1 {
					rep.SmartAppControl = "1 (ON - unsigned EXEs require code signing or .cmd launch)"
				} else {
					rep.SmartAppControl = fmt.Sprintf("%d (OFF)", *parsed.SAC)
				}
			} else {
				rep.SmartAppControl = "unknown"
			}
			rep.ExecPolicy = parsed.EP
		}
	}

	if vPath, vErr := exec.LookPath("vulkaninfo.exe"); vErr == nil {
		rep.VulkanOK = true
		rep.VulkanNote = "vulkaninfo found at " + vPath
	} else {
		rep.VulkanNote = "vulkaninfo.exe not on PATH (Adrenalin Vulkan ICD usually still works)"
	}

	rep.LlamaBinaryPath = findLlamaBinary(installDir, []string{"llama-server.exe", "llama.exe"})
	rep.Tools = checkTools([]string{"llama-server.exe", "llama.exe", "node", "pi.cmd", "uv", "git"})
}

func detectLinux(rep *SystemReport, installDir string) {
	// Check DRM sysfs nodes for 1002:73df
	cards, _ := filepath.Glob("/sys/class/drm/card*/device")
	for _, dev := range cards {
		ven, errV := os.ReadFile(filepath.Join(dev, "vendor"))
		devID, errD := os.ReadFile(filepath.Join(dev, "device"))
		if errV == nil && errD == nil {
			vStr := strings.TrimSpace(string(ven))
			dStr := strings.TrimSpace(string(devID))
			if ParseLinuxPCIDevice(vStr, dStr) {
				rep.HasRX6700XT = true
				rep.GPUs = append(rep.GPUs, fmt.Sprintf("AMD Radeon RX 6700 XT (%s:%s) [Navi 22 / gfx1031]", vStr, dStr))
			} else {
				rep.GPUs = append(rep.GPUs, fmt.Sprintf("DRM GPU (%s:%s)", vStr, dStr))
			}
		}
	}

	if len(rep.GPUs) == 0 {
		if lspciOut, err := exec.Command("lspci").Output(); err == nil {
			for _, line := range strings.Split(string(lspciOut), "\n") {
				if strings.Contains(line, "VGA") || strings.Contains(line, "Display") || strings.Contains(line, "3D") {
					if IsRX6700XTID(line) {
						rep.HasRX6700XT = true
					}
					rep.GPUs = append(rep.GPUs, strings.TrimSpace(line))
				}
			}
		}
	}

	if memRaw, err := os.ReadFile("/proc/meminfo"); err == nil {
		for _, line := range strings.Split(string(memRaw), "\n") {
			if strings.HasPrefix(line, "MemTotal:") {
				fields := strings.Fields(line)
				if len(fields) >= 2 {
					if kb, pErr := strconv.ParseFloat(fields[1], 64); pErr == nil {
						rep.TotalRAMGiB = kb / (1024 * 1024)
					}
				}
				break
			}
		}
	}

	if vPath, vErr := exec.LookPath("vulkaninfo"); vErr == nil {
		rep.VulkanOK = true
		rep.VulkanNote = "vulkaninfo found at " + vPath
	} else {
		rep.VulkanNote = "vulkaninfo not found (install vulkan-tools + mesa-vulkan-drivers)"
	}

	if rPath, rErr := exec.LookPath("rocminfo"); rErr == nil {
		rep.ROCmNote = "rocminfo at " + rPath + " (for gfx1031 set HSA_OVERRIDE_GFX_VERSION=10.3.0)"
	} else {
		rep.ROCmNote = "rocminfo not installed (Vulkan backend requires no ROCm stack)"
	}

	rep.LlamaBinaryPath = findLlamaBinary(installDir, []string{"llama-server", "llama"})
	rep.Tools = checkTools([]string{"llama-server", "node", "pi", "uv", "git", "curl"})
}

func findLlamaBinary(installDir string, names []string) string {
	candidates := []string{}
	for _, n := range names {
		candidates = append(candidates,
			filepath.Join(installDir, "bin", "vulkan", n),
			filepath.Join(installDir, "bin", n),
		)
		if runtime.GOOS == "windows" {
			candidates = append(candidates, filepath.Join(`C:\llama.cpp`, n))
		}
		if p, err := exec.LookPath(n); err == nil {
			candidates = append(candidates, p)
		}
	}
	for _, c := range candidates {
		if info, err := os.Stat(c); err == nil && !info.IsDir() {
			return c
		}
	}
	return ""
}

func checkTools(names []string) []ToolCheck {
	out := make([]ToolCheck, 0, len(names))
	for _, n := range names {
		p, err := exec.LookPath(n)
		out = append(out, ToolCheck{
			Name:  n,
			Found: err == nil,
			Path:  p,
		})
	}
	return out
}

// FormatReport renders a clean plain-English summary of system readiness.
func FormatReport(rep SystemReport) string {
	var b strings.Builder
	fmt.Fprintf(&b, "Host      : %s (%s/%s)\n", rep.Hostname, rep.OS, rep.Arch)
	if rep.TotalRAMGiB > 0 {
		fmt.Fprintf(&b, "System RAM: %.1f GiB\n", rep.TotalRAMGiB)
	}
	for _, c := range rep.CPUs {
		fmt.Fprintf(&b, "CPU       : %s\n", c)
	}
	if len(rep.GPUs) == 0 {
		fmt.Fprintf(&b, "GPU       : None detected via OS query\n")
	} else {
		for _, g := range rep.GPUs {
			fmt.Fprintf(&b, "GPU       : %s\n", g)
		}
	}
	if rep.HasRX6700XT {
		fmt.Fprintf(&b, "Target GPU: RX 6700 XT confirmed (12 GB GDDR6, ~384 GB/s, Navi 22 / gfx1031)\n")
	} else {
		fmt.Fprintf(&b, "Target GPU: RX 6700 XT not detected (installer still runs on any Vulkan GPU)\n")
	}
	fmt.Fprintf(&b, "Vulkan    : %s\n", rep.VulkanNote)
	if rep.ROCmNote != "" {
		fmt.Fprintf(&b, "ROCm      : %s\n", rep.ROCmNote)
	}
	if rep.OS == "windows" {
		fmt.Fprintf(&b, "SAC State : %s\n", rep.SmartAppControl)
		fmt.Fprintf(&b, "PS Policy : %s\n", rep.ExecPolicy)
	}
	if rep.LlamaBinaryPath != "" {
		fmt.Fprintf(&b, "llama.cpp : %s\n", rep.LlamaBinaryPath)
	} else {
		fmt.Fprintf(&b, "llama.cpp : Not found in install dir or PATH\n")
	}
	fmt.Fprintf(&b, "Tools     :")
	for _, t := range rep.Tools {
		mark := "missing"
		if t.Found {
			mark = "OK"
		}
		fmt.Fprintf(&b, " %s=%s", t.Name, mark)
	}
	fmt.Fprintln(&b)
	return b.String()
}
