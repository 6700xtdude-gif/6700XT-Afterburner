package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/charmbracelet/huh"
	"github.com/charmbracelet/lipgloss"
)

const installerVersion = "1.0.0"

var (
	headerStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("205")).
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("63")).
			Padding(0, 2)

	okStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("42")).Bold(true)
	errStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("196")).Bold(true)
	infoStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("39"))
)

func resolveDefaultInstallDir() string {
	for _, candidate := range []string{".", ".."} {
		if _, err := os.Stat(filepath.Join(candidate, "start_local_server.ps1")); err == nil {
			if abs, aErr := filepath.Abs(candidate); aErr == nil {
				return abs
			}
		}
	}
	abs, err := filepath.Abs("./rx6700xt-ai")
	if err != nil {
		return "./rx6700xt-ai"
	}
	return abs
}

func waitEnter() {
	fmt.Print("\nPress Enter to return to menu...")
	_, _ = bufio.NewReader(os.Stdin).ReadString('\n')
}

func main() {
	showVer := flag.Bool("version", false, "Print installer version and exit")
	runCheck := flag.Bool("check", false, "Run non-interactive hardware/driver/tool check and exit")
	dirFlag := flag.String("dir", "", "Target installation directory (default: Afterburner repo or ./rx6700xt-ai)")
	flag.Parse()

	if *showVer {
		fmt.Printf("rx6700xt-installer v%s (%s/%s)\n", installerVersion, runtime.GOOS, runtime.GOARCH)
		return
	}

	installDir := strings.TrimSpace(*dirFlag)
	if installDir == "" {
		installDir = resolveDefaultInstallDir()
	} else if abs, err := filepath.Abs(installDir); err == nil {
		installDir = abs
	}

	if *runCheck {
		rep := DetectSystem(installDir)
		fmt.Print(FormatReport(rep))
		return
	}

	for {
		fmt.Println()
		banner := fmt.Sprintf("6700XT-Afterburner Installer v%s  |  %s/%s\nInstall Dir: %s",
			installerVersion, runtime.GOOS, runtime.GOARCH, installDir)
		fmt.Println(headerStyle.Render(banner))

		var choice string
		form := huh.NewForm(
			huh.NewGroup(
				huh.NewSelect[string]().
					Title("Select an action").
					Options(
						huh.NewOption("1. Hardware & Driver Check (RX 6700 XT / Vulkan / ROCm / Tools)", "check"),
						huh.NewOption("2. Install Official llama.cpp (Vulkan x64)", "llama"),
						huh.NewOption("3. Download Starter GGUF Models (12 GB VRAM Curated)", "models"),
						huh.NewOption("4. Configure Pi Coding Agent (pi.dev) + Launchers", "pi"),
						huh.NewOption("5. Generate Open WebUI Launcher (uvx -> port 3000)", "webui"),
						huh.NewOption("6. Quit", "quit"),
					).
					Value(&choice),
			),
		)

		if err := form.Run(); err != nil {
			fmt.Println(errStyle.Render("Menu canceled: " + err.Error()))
			return
		}

		switch choice {
		case "quit":
			return

		case "check":
			rep := DetectSystem(installDir)
			fmt.Println(infoStyle.Render("\n--- System & GPU Readiness ---"))
			fmt.Print(FormatReport(rep))
			waitEnter()

		case "llama":
			dest, err := InstallLlamaCpp(installDir, runtime.GOOS, runtime.GOARCH)
			if err != nil {
				fmt.Println(errStyle.Render("llama.cpp install failed: " + err.Error()))
			} else {
				fmt.Println(okStyle.Render("Installed llama.cpp Vulkan binaries into: " + dest))
			}
			waitEnter()

		case "models":
			opts := make([]huh.Option[string], 0, len(CuratedModels))
			for _, m := range CuratedModels {
				opts = append(opts, huh.NewOption(m.DisplayName+" — "+m.Note, m.ID))
			}
			var selected []string
			msForm := huh.NewForm(
				huh.NewGroup(
					huh.NewMultiSelect[string]().
						Title("Choose RX 6700 XT 12 GB GGUF models to download").
						Options(opts...).
						Value(&selected),
				),
			)
			if err := msForm.Run(); err != nil {
				fmt.Println(errStyle.Render("Selection canceled: " + err.Error()))
				waitEnter()
				continue
			}
			modelsDir := filepath.Join(installDir, "models")
			for _, id := range selected {
				for _, m := range CuratedModels {
					if m.ID == id {
						path, err := DownloadModel(modelsDir, m)
						if err != nil {
							fmt.Println(errStyle.Render(fmt.Sprintf("Failed %s: %v", m.Filename, err)))
						} else {
							fmt.Println(okStyle.Render("Ready: " + path))
						}
					}
				}
			}
			waitEnter()

		case "pi":
			var runPiInstall bool
			cForm := huh.NewForm(
				huh.NewGroup(
					huh.NewConfirm().
						Title("Install or update the Pi CLI binary from pi.dev first?").
						Affirmative("Yes, install Pi").
						Negative("Skip CLI install (configs + launchers only)").
						Value(&runPiInstall),
				),
			)
			if err := cForm.Run(); err != nil {
				fmt.Println(errStyle.Render("Canceled: " + err.Error()))
				waitEnter()
				continue
			}
			if runPiInstall {
				if err := InstallPiBinary(); err != nil {
					fmt.Println(errStyle.Render("Pi CLI install failed: " + err.Error()))
					waitEnter()
					continue
				}
			}
			agentDir, err := ConfigurePi(installDir, runtime.GOOS)
			if err != nil {
				fmt.Println(errStyle.Render("Pi config failed: " + err.Error()))
				waitEnter()
				continue
			}
			launchers, err := GenerateLaunchers(installDir, runtime.GOOS)
			if err != nil {
				fmt.Println(errStyle.Render("Launcher generation failed: " + err.Error()))
			} else {
				fmt.Println(okStyle.Render("Configured Pi at: " + agentDir))
				for _, l := range launchers {
					fmt.Println(infoStyle.Render("  Launcher: " + l))
				}
			}
			waitEnter()

		case "webui":
			launchers, err := GenerateLaunchers(installDir, runtime.GOOS)
			if err != nil {
				fmt.Println(errStyle.Render("Launcher generation failed: " + err.Error()))
			} else {
				fmt.Println(okStyle.Render("Generated launchers (start Open WebUI via uvx on port 3000):"))
				for _, l := range launchers {
					fmt.Println(infoStyle.Render("  " + l))
				}
			}
			waitEnter()
		}
	}
}
