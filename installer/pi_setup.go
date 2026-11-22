package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// PiSettings represents ~/.pi/agent/settings.json.
type PiSettings struct {
	DefaultProvider string   `json:"defaultProvider"`
	DefaultModel    string   `json:"defaultModel"`
	DefaultTools    []string `json:"defaultTools"`
}

// BuildPiSettings returns OS-appropriate tool settings (Windows excludes bash to avoid shell hangs).
func BuildPiSettings(goos, defaultProvider, defaultModel string) PiSettings {
	tools := []string{"read", "bash", "edit", "write"}
	if goos == "windows" {
		tools = []string{"read", "powershell", "edit", "write"}
	}
	return PiSettings{
		DefaultProvider: defaultProvider,
		DefaultModel:    defaultModel,
		DefaultTools:    tools,
	}
}

type piCost struct {
	Input      float64 `json:"input"`
	Output     float64 `json:"output"`
	CacheRead  float64 `json:"cacheRead"`
	CacheWrite float64 `json:"cacheWrite"`
}

type piModelEntry struct {
	ID            string `json:"id"`
	Name          string `json:"name"`
	ContextWindow int    `json:"contextWindow"`
	MaxTokens     int    `json:"maxTokens"`
	Cost          piCost `json:"cost"`
}

type piProviderEntry struct {
	Name    string         `json:"name"`
	BaseURL string         `json:"baseUrl"`
	API     string         `json:"api"`
	APIKey  string         `json:"apiKey"`
	Models  []piModelEntry `json:"models"`
}

type piModelsFile struct {
	Schema    string                     `json:"$schema"`
	Providers map[string]piProviderEntry `json:"providers"`
}

// WriteFileNoBOM writes UTF-8 text strictly without a UTF-8 BOM (EF BB BF).
func WriteFileNoBOM(path string, data []byte, perm os.FileMode) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, data, perm)
}

func backupIfExists(agentDir string, files []string) {
	stamp := time.Now().Format("20060102_150405")
	backupDir := filepath.Join(agentDir, "backup_"+stamp)
	created := false
	for _, name := range files {
		src := filepath.Join(agentDir, name)
		data, err := os.ReadFile(src)
		if err != nil {
			continue
		}
		if !created {
			if err := os.MkdirAll(backupDir, 0o755); err != nil {
				return
			}
			created = true
		}
		_ = os.WriteFile(filepath.Join(backupDir, name), data, 0o644)
	}
}

// InstallPiBinary runs the official pi.dev installer non-interactively and cleans blocked shims on Windows.
func InstallPiBinary() error {
	if runtime.GOOS == "windows" {
		psCmd := `$ErrorActionPreference = 'Stop'
$tmp = Join-Path $env:TEMP ("pi-install-" + $PID + ".ps1")
try {
    $script = Invoke-RestMethod -Uri 'https://pi.dev/install.ps1' -TimeoutSec 30
    [System.IO.File]::WriteAllText($tmp, $script, (New-Object System.Text.UTF8Encoding($false)))
    "" | & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $tmp
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}`
		cmd := exec.Command("powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", psCmd)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			return err
		}
		cleanupWindowsPiShim()
		return nil
	}

	cmd := exec.Command("sh", "-c", "curl -fsSL https://pi.dev/install.sh | sh")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func cleanupWindowsPiShim() {
	home, err := os.UserHomeDir()
	if err != nil {
		return
	}
	binDir := filepath.Join(home, ".pi", "agent", "bin")
	cmdShim := filepath.Join(binDir, "pi.cmd")
	ps1Shim := filepath.Join(binDir, "pi.ps1")
	if _, err := os.Stat(cmdShim); err != nil {
		return
	}
	if _, err := os.Stat(ps1Shim); err != nil {
		return
	}
	out, err := exec.Command("powershell.exe", "-NoProfile", "-Command",
		`$m=@{}; foreach ($r in Get-ExecutionPolicy -List){$m[$r.Scope.ToString()]=$r.ExecutionPolicy.ToString()}; $ep='Restricted'; foreach ($s in 'MachinePolicy','UserPolicy','CurrentUser','LocalMachine'){if($m[$s] -and $m[$s] -ne 'Undefined'){$ep=$m[$s];break}}; Write-Output $ep`).Output()
	if err == nil {
		ep := strings.TrimSpace(string(out))
		if ep == "Restricted" || ep == "AllSigned" {
			_ = os.Remove(ps1Shim)
			fmt.Printf("Removed blocked pi.ps1 shim (persistent ExecutionPolicy=%s; kept pi.cmd)\n", ep)
		}
	}
}

// ConfigurePi writes UTF-8 (no BOM) models.json, settings.json, and AGENTS.md into ~/.pi/agent.
func ConfigurePi(installDir string, goos string) (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	agentDir := filepath.Join(home, ".pi", "agent")
	backupIfExists(agentDir, []string{"models.json", "settings.json", "AGENTS.md"})

	modelsDir := filepath.Join(installDir, "models")
	discovered := DiscoverGGUFs(modelsDir)
	if len(discovered) == 0 {
		discovered = []string{
			"qwen2.5-coder-7b-instruct-q4_k_m",
			"Qwen3-8B-Q4_K_M",
			"Qwen3-14B-Q4_K_M",
		}
	}

	entries := make([]piModelEntry, 0, len(discovered))
	for _, id := range discovered {
		entries = append(entries, piModelEntry{
			ID:            id,
			Name:          id,
			ContextWindow: 32768,
			MaxTokens:     4096,
		})
	}

	modelsCfg := piModelsFile{
		Schema: "https://pi.dev/schemas/models.schema.json",
		Providers: map[string]piProviderEntry{
			"afterburner": {
				Name:    "RX 6700 XT AfterBurner Vulkan Router (127.0.0.1:8080)",
				BaseURL: "http://127.0.0.1:8080/v1",
				API:     "openai-completions",
				APIKey:  "local",
				Models:  entries,
			},
		},
	}

	modelsBytes, err := json.MarshalIndent(modelsCfg, "", "  ")
	if err != nil {
		return "", err
	}
	modelsBytes = append(modelsBytes, '\n')
	if err := WriteFileNoBOM(filepath.Join(agentDir, "models.json"), modelsBytes, 0o644); err != nil {
		return "", err
	}

	settings := BuildPiSettings(goos, "afterburner", discovered[0])
	settingsBytes, err := json.MarshalIndent(settings, "", "  ")
	if err != nil {
		return "", err
	}
	settingsBytes = append(settingsBytes, '\n')
	if err := WriteFileNoBOM(filepath.Join(agentDir, "settings.json"), settingsBytes, 0o644); err != nil {
		return "", err
	}

	var agentsContent string
	if goos == "windows" {
		agentsContent = `# Agent Operating Guidelines

- Platform: Windows host environment (RX 6700 XT 12 GB Vulkan).
- Tools: Use ` + "`powershell`" + ` and file tools (` + "`read`" + `, ` + "`edit`" + `, ` + "`write`" + `) directly. The ` + "`bash`" + ` tool is excluded on Windows.
- PowerShell Output Hygiene: Always filter and cap command output (` + "`Where-Object`" + `, ` + "`Select-Object -First 30`" + `, ` + "`-ErrorAction SilentlyContinue`" + `). Never run unfiltered loops over the registry or ` + "`C:\\`" + `.
- PowerShell 5.1 Output Flush Rule: NEVER end a command with bare ` + "`Select-Object ...`" + ` -- Windows PowerShell 5.1 buffers implicit tables and Pi's exit wrapper drops stdout to empty. Always end pipelines with ` + "`| Format-Table -AutoSize | Out-String`" + `, ` + "`| Format-List`" + `, or ` + "`| ConvertTo-Json`" + `.
- Grounding: Base every answer on verified command output; report errors verbatim.
`
	} else {
		agentsContent = `# Agent Operating Guidelines

- Platform: Linux host environment (RX 6700 XT 12 GB Vulkan).
- Tools: Use ` + "`bash`" + ` and file tools (` + "`read`" + `, ` + "`edit`" + `, ` + "`write`" + `) directly.
- Output Hygiene: Filter and cap large directory or log listings (` + "`head -n 40`" + `, ` + "`rg`" + `) to keep context clean.
- Grounding: Base every answer on verified command output; report errors verbatim.
`
	}
	if err := WriteFileNoBOM(filepath.Join(agentDir, "AGENTS.md"), []byte(agentsContent), 0o644); err != nil {
		return "", err
	}
	return agentDir, nil
}

// GenerateLaunchers creates OS-native router, speculative, and Open WebUI launcher scripts in installDir.
func GenerateLaunchers(installDir, goos string) ([]string, error) {
	if err := os.MkdirAll(installDir, 0o755); err != nil {
		return nil, err
	}
	modelsDir := filepath.Join(installDir, "models")
	vulkanDir := filepath.Join(installDir, "bin", "vulkan")
	var created []string

	if goos == "windows" {
		routerCmd := filepath.Join(installDir, "start-afterburner-router.cmd")
		routerBody := fmt.Sprintf(`@echo off
setlocal
set "LLAMA_BIN=%s\llama-server.exe"
if exist "%s\llama.exe" set "LLAMA_BIN=%s\llama.exe"
"%%LLAMA_BIN%%" --models-dir "%s" --models-max 1 --host 127.0.0.1 --port 8080 -ngl 99 -c 32768 -fa on -ctk q4_0 -ctv q4_0 --jinja
`, vulkanDir, vulkanDir, vulkanDir, modelsDir)
		if err := WriteFileNoBOM(routerCmd, []byte(strings.ReplaceAll(routerBody, "\n", "\r\n")), 0o644); err != nil {
			return nil, err
		}
		created = append(created, routerCmd)

		specCmd := filepath.Join(installDir, "start-afterburner-speculative.cmd")
		specBody := fmt.Sprintf(`@echo off
setlocal
"%s\llama-server.exe" -m "%s\qwen2.5-coder-7b-instruct-q4_k_m.gguf" -md "%s\qwen2.5-coder-0.5b-instruct-q4_0.gguf" --host 127.0.0.1 --port 8080 -ngl 99 -ngld 99 --spec-type draft-simple --spec-draft-n-max 3 -fa on -ctk q4_0 -ctv q4_0 -c 32768 -t 6
`, vulkanDir, modelsDir, modelsDir)
		if err := WriteFileNoBOM(specCmd, []byte(strings.ReplaceAll(specBody, "\n", "\r\n")), 0o644); err != nil {
			return nil, err
		}
		created = append(created, specCmd)

		webuiCmd := filepath.Join(installDir, "start-openwebui.cmd")
		webuiData := filepath.Join(installDir, "openwebui-data")
		webuiBody := fmt.Sprintf(`@echo off
setlocal
set OPENAI_API_BASE_URLS=http://127.0.0.1:8080/v1
set OPENAI_API_KEYS=local
set DATA_DIR=%s
uvx --python 3.11 open-webui serve --port 3000
`, webuiData)
		if err := WriteFileNoBOM(webuiCmd, []byte(strings.ReplaceAll(webuiBody, "\n", "\r\n")), 0o644); err != nil {
			return nil, err
		}
		created = append(created, webuiCmd)
	} else {
		routerSh := filepath.Join(installDir, "start-afterburner-router.sh")
		routerBody := fmt.Sprintf(`#!/usr/bin/env bash
set -euo pipefail
LLAMA_BIN="%s/llama-server"
if [ ! -x "$LLAMA_BIN" ]; then LLAMA_BIN="%s/llama"; fi
exec "$LLAMA_BIN" --models-dir "%s" --models-max 1 --host 127.0.0.1 --port 8080 -ngl 99 -c 32768 -fa on -ctk q4_0 -ctv q4_0 --jinja
`, vulkanDir, vulkanDir, modelsDir)
		if err := WriteFileNoBOM(routerSh, []byte(routerBody), 0o755); err != nil {
			return nil, err
		}
		created = append(created, routerSh)

		specSh := filepath.Join(installDir, "start-afterburner-speculative.sh")
		specBody := fmt.Sprintf(`#!/usr/bin/env bash
set -euo pipefail
exec "%s/llama-server" -m "%s/qwen2.5-coder-7b-instruct-q4_k_m.gguf" -md "%s/qwen2.5-coder-0.5b-instruct-q4_0.gguf" --host 127.0.0.1 --port 8080 -ngl 99 -ngld 99 --spec-type draft-simple --spec-draft-n-max 3 -fa on -ctk q4_0 -ctv q4_0 -c 32768 -t 6
`, vulkanDir, modelsDir, modelsDir)
		if err := WriteFileNoBOM(specSh, []byte(specBody), 0o755); err != nil {
			return nil, err
		}
		created = append(created, specSh)

		webuiSh := filepath.Join(installDir, "start-openwebui.sh")
		webuiData := filepath.Join(installDir, "openwebui-data")
		webuiBody := fmt.Sprintf(`#!/usr/bin/env bash
set -euo pipefail
export OPENAI_API_BASE_URLS="http://127.0.0.1:8080/v1"
export OPENAI_API_KEYS="local"
export DATA_DIR="%s"
exec uvx --python 3.11 open-webui serve --port 3000
`, webuiData)
		if err := WriteFileNoBOM(webuiSh, []byte(webuiBody), 0o755); err != nil {
			return nil, err
		}
		created = append(created, webuiSh)
	}
	return created, nil
}
