package main

import (
	"archive/tar"
	"archive/zip"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const llamaReleasesURL = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=15"

// GHAsset represents a single asset from the GitHub Releases API.
type GHAsset struct {
	Name               string `json:"name"`
	BrowserDownloadURL string `json:"browser_download_url"`
	Size               int64  `json:"size"`
}

// GHRelease represents a GitHub release entry.
type GHRelease struct {
	TagName    string    `json:"tag_name"`
	Prerelease bool      `json:"prerelease"`
	Draft      bool      `json:"draft"`
	Assets     []GHAsset `json:"assets"`
}

// SelectVulkanAsset picks the matching official Vulkan x64 release archive for the target OS/arch.
func SelectVulkanAsset(assets []GHAsset, goos, goarch string) (GHAsset, error) {
	if goarch != "amd64" {
		return GHAsset{}, fmt.Errorf("unsupported architecture %q (expected amd64)", goarch)
	}
	var wantTokens []string
	var ext string
	switch goos {
	case "windows":
		wantTokens = []string{"bin-win-vulkan-x64"}
		ext = ".zip"
	case "linux":
		wantTokens = []string{"bin-ubuntu-vulkan-x64"}
		ext = ".tar.gz"
	default:
		return GHAsset{}, fmt.Errorf("unsupported OS %q", goos)
	}

	for _, a := range assets {
		lower := strings.ToLower(a.Name)
		if !strings.HasSuffix(lower, ext) {
			continue
		}
		matched := true
		for _, tok := range wantTokens {
			if !strings.Contains(lower, tok) {
				matched = false
				break
			}
		}
		if matched {
			return a, nil
		}
	}
	return GHAsset{}, fmt.Errorf("no matching Vulkan x64 asset found for %s/%s", goos, goarch)
}

// FetchLatestVulkanRelease queries recent llama.cpp releases (skipping asset-empty tags like v1.0.0)
// and returns the newest release + asset matching goos/goarch.
func FetchLatestVulkanRelease(goos, goarch string) (GHRelease, GHAsset, error) {
	client := &http.Client{Timeout: 30 * time.Second}
	req, err := http.NewRequest(http.MethodGet, llamaReleasesURL, nil)
	if err != nil {
		return GHRelease{}, GHAsset{}, err
	}
	req.Header.Set("User-Agent", "rx6700xt-afterburner-installer")
	req.Header.Set("Accept", "application/vnd.github+json")

	resp, err := client.Do(req)
	if err != nil {
		return GHRelease{}, GHAsset{}, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return GHRelease{}, GHAsset{}, fmt.Errorf("GitHub API returned HTTP %d", resp.StatusCode)
	}

	var releases []GHRelease
	if err := json.NewDecoder(resp.Body).Decode(&releases); err != nil {
		return GHRelease{}, GHAsset{}, err
	}
	for _, rel := range releases {
		if rel.Draft {
			continue
		}
		if asset, err := SelectVulkanAsset(rel.Assets, goos, goarch); err == nil {
			return rel, asset, nil
		}
	}
	return GHRelease{}, GHAsset{}, fmt.Errorf("no recent llama.cpp release contains a Vulkan x64 binary for %s/%s", goos, goarch)
}

// InstallLlamaCpp downloads and extracts the official Vulkan llama.cpp release into <installDir>/bin/vulkan.
func InstallLlamaCpp(installDir, goos, goarch string) (string, error) {
	rel, asset, err := FetchLatestVulkanRelease(goos, goarch)
	if err != nil {
		return "", err
	}

	destDir := filepath.Join(installDir, "bin", "vulkan")
	if err := os.MkdirAll(destDir, 0o755); err != nil {
		return "", err
	}

	tmpArchive := filepath.Join(os.TempDir(), asset.Name+".part")
	fmt.Printf("Downloading llama.cpp %s (%s, %.1f MB)...\n", rel.TagName, asset.Name, float64(asset.Size)/(1024*1024))
	if err := downloadWithProgress(asset.BrowserDownloadURL, tmpArchive, asset.Size, false); err != nil {
		return "", err
	}
	defer os.Remove(tmpArchive)

	fmt.Printf("Extracting %s into %s...\n", asset.Name, destDir)
	if strings.HasSuffix(strings.ToLower(asset.Name), ".zip") {
		if err := extractZip(tmpArchive, destDir); err != nil {
			return "", err
		}
	} else if strings.HasSuffix(strings.ToLower(asset.Name), ".tar.gz") {
		if err := extractTarGz(tmpArchive, destDir); err != nil {
			return "", err
		}
	} else {
		return "", fmt.Errorf("unsupported archive format: %s", asset.Name)
	}

	return destDir, nil
}

func resolveArchiveTarget(destDir, entryName string) (string, error) {
	clean := filepath.Clean(entryName)
	if clean == "." || clean == "" || filepath.IsAbs(clean) || strings.HasPrefix(clean, "..") {
		return "", fmt.Errorf("invalid archive entry path: %q", entryName)
	}
	target := filepath.Join(destDir, clean)
	rel, err := filepath.Rel(destDir, target)
	if err != nil || strings.HasPrefix(rel, "..") {
		return "", fmt.Errorf("archive path escapes target dir: %q", entryName)
	}
	return target, nil
}

func extractZip(zipPath, destDir string) error {
	r, err := zip.OpenReader(zipPath)
	if err != nil {
		return err
	}
	defer r.Close()

	for _, f := range r.File {
		target, err := resolveArchiveTarget(destDir, f.Name)
		if err != nil {
			return err
		}
		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(target, 0o755); err != nil {
				return err
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
			return err
		}
		rc, err := f.Open()
		if err != nil {
			return err
		}
		out, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, f.Mode()|0o644)
		if err != nil {
			rc.Close()
			return err
		}
		_, copyErr := io.Copy(out, rc)
		rc.Close()
		out.Close()
		if copyErr != nil {
			return copyErr
		}
	}
	return nil
}

func extractTarGz(tgzPath, destDir string) error {
	f, err := os.Open(tgzPath)
	if err != nil {
		return err
	}
	defer f.Close()

	gz, err := gzip.NewReader(f)
	if err != nil {
		return err
	}
	defer gz.Close()

	tr := tar.NewReader(gz)
	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
		target, err := resolveArchiveTarget(destDir, hdr.Name)
		if err != nil {
			return err
		}
		switch hdr.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(target, 0o755); err != nil {
				return err
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
				return err
			}
			mode := os.FileMode(hdr.Mode) & 0o777
			if mode == 0 {
				mode = 0o755
			}
			out, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, mode)
			if err != nil {
				return err
			}
			_, copyErr := io.Copy(out, tr)
			out.Close()
			if copyErr != nil {
				return copyErr
			}
		case tar.TypeSymlink:
			if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
				return err
			}
			_ = os.Remove(target)
			if err := os.Symlink(hdr.Linkname, target); err != nil {
				return err
			}
		}
	}
	return nil
}
