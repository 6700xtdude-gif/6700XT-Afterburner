package main

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func TestSelectVulkanAsset(t *testing.T) {
	sample := []GHAsset{
		{Name: "llama-b12608-bin-win-cpu-x64.zip", Size: 100},
		{Name: "llama-b12608-bin-win-vulkan-arm64.zip", Size: 200},
		{Name: "llama-b12608-bin-win-vulkan-x64.zip", Size: 300},
		{Name: "llama-b12608-bin-ubuntu-vulkan-arm64.tar.gz", Size: 400},
		{Name: "llama-b12608-bin-ubuntu-vulkan-x64.tar.gz", Size: 500},
	}

	winAsset, err := SelectVulkanAsset(sample, "windows", "amd64")
	if err != nil {
		t.Fatalf("windows/amd64 unexpected error: %v", err)
	}
	if winAsset.Name != "llama-b12608-bin-win-vulkan-x64.zip" {
		t.Fatalf("got %s, want llama-b12608-bin-win-vulkan-x64.zip", winAsset.Name)
	}

	linAsset, err := SelectVulkanAsset(sample, "linux", "amd64")
	if err != nil {
		t.Fatalf("linux/amd64 unexpected error: %v", err)
	}
	if linAsset.Name != "llama-b12608-bin-ubuntu-vulkan-x64.tar.gz" {
		t.Fatalf("got %s, want llama-b12608-bin-ubuntu-vulkan-x64.tar.gz", linAsset.Name)
	}

	if _, err := SelectVulkanAsset(sample, "windows", "arm64"); err == nil {
		t.Fatalf("expected error for unsupported arch arm64")
	}
}

func TestParseLinuxPCIDeviceAndIsRX6700XT(t *testing.T) {
	if !ParseLinuxPCIDevice("0x1002\n", "0x73df\n") {
		t.Fatalf("expected 0x1002 / 0x73df to match RX 6700 XT")
	}
	if ParseLinuxPCIDevice("0x10de", "0x2484") {
		t.Fatalf("unexpected match for NVIDIA device")
	}
	if !IsRX6700XTID(`PCI\VEN_1002&DEV_73DF&SUBSYS_2310148C`) {
		t.Fatalf("expected Windows PNPDeviceID to match RX 6700 XT")
	}
	if !IsRX6700XTID("AMD Radeon RX 6700 XT") {
		t.Fatalf("expected GPU display name to match RX 6700 XT")
	}
}

func TestBuildPiSettings(t *testing.T) {
	win := BuildPiSettings("windows", "afterburner", "Qwen3-8B-Q4_K_M")
	wantWin := []string{"read", "powershell", "edit", "write"}
	if !reflect.DeepEqual(win.DefaultTools, wantWin) {
		t.Fatalf("windows tools = %v, want %v", win.DefaultTools, wantWin)
	}
	for _, tool := range win.DefaultTools {
		if tool == "bash" {
			t.Fatalf("windows tools must exclude bash")
		}
	}

	lin := BuildPiSettings("linux", "afterburner", "Qwen3-8B-Q4_K_M")
	wantLin := []string{"read", "bash", "edit", "write"}
	if !reflect.DeepEqual(lin.DefaultTools, wantLin) {
		t.Fatalf("linux tools = %v, want %v", lin.DefaultTools, wantLin)
	}
}

func TestWriteFileNoBOMAndLaunchers(t *testing.T) {
	tmp := t.TempDir()
	jsonPath := filepath.Join(tmp, "sub", "settings.json")
	if err := WriteFileNoBOM(jsonPath, []byte("{\"ok\":true}\n"), 0o644); err != nil {
		t.Fatalf("WriteFileNoBOM error: %v", err)
	}
	raw, err := os.ReadFile(jsonPath)
	if err != nil {
		t.Fatalf("ReadFile error: %v", err)
	}
	if len(raw) >= 3 && raw[0] == 0xEF && raw[1] == 0xBB && raw[2] == 0xBF {
		t.Fatalf("unexpected UTF-8 BOM in %s", jsonPath)
	}

	winLaunchers, err := GenerateLaunchers(filepath.Join(tmp, "win"), "windows")
	if err != nil || len(winLaunchers) != 3 {
		t.Fatalf("windows GenerateLaunchers = (%v, %v), want 3 files", winLaunchers, err)
	}
	linLaunchers, err := GenerateLaunchers(filepath.Join(tmp, "lin"), "linux")
	if err != nil || len(linLaunchers) != 3 {
		t.Fatalf("linux GenerateLaunchers = (%v, %v), want 3 files", linLaunchers, err)
	}
	routerSh, err := os.ReadFile(linLaunchers[0])
	if err != nil {
		t.Fatalf("read router sh: %v", err)
	}
	if !strings.Contains(string(routerSh), "-ctk q4_0 -ctv q4_0") {
		t.Fatalf("expected q4_0 KV flags in %s", linLaunchers[0])
	}
}
