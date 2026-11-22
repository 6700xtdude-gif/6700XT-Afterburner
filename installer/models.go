package main

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// CuratedModel describes a verified RX 6700 XT 12 GB GGUF weight file on Hugging Face.
type CuratedModel struct {
	ID          string
	DisplayName string
	Filename    string
	URL         string
	ExpectedSz  int64
	Note        string
}

// CuratedModels holds the 5 verified GGUFs tuned for 12 GB RX 6700 XT VRAM.
var CuratedModels = []CuratedModel{
	{
		ID:          "qwen2.5-coder-7b-q4km",
		DisplayName: "Qwen2.5-Coder-7B-Instruct (Q4_K_M, 4.36 GiB)",
		Filename:    "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
		URL:         "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
		ExpectedSz:  4683073536,
		Note:        "Primary coding verifier (72 t/s solo; up to 95.3 t/s JSON / 85.3 t/s code with 0.5B draft)",
	},
	{
		ID:          "qwen2.5-coder-0.5b-q40",
		DisplayName: "Qwen2.5-Coder-0.5B-Instruct (Q4_0, 409 MiB)",
		Filename:    "qwen2.5-coder-0.5b-instruct-q4_0.gguf",
		URL:         "https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-0.5b-instruct-q4_0.gguf",
		ExpectedSz:  428730240,
		Note:        "Stock 24L speculative drafter for Qwen2.5-Coder 7B & 14B",
	},
	{
		ID:          "qwen2.5-coder-14b-q4km",
		DisplayName: "Qwen2.5-Coder-14B-Instruct (Q4_K_M, 8.37 GiB)",
		Filename:    "qwen2.5-coder-14b-instruct-q4_k_m.gguf",
		URL:         "https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct-GGUF/resolve/main/qwen2.5-coder-14b-instruct-q4_k_m.gguf",
		ExpectedSz:  8988110272,
		Note:        "Heavy coding verifier (100% VRAM + 0.5B draft = 60.9 t/s code)",
	},
	{
		ID:          "qwen3-8b-q4km",
		DisplayName: "Qwen3-8B (Q4_K_M, 4.68 GiB)",
		Filename:    "Qwen3-8B-Q4_K_M.gguf",
		URL:         "https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf",
		ExpectedSz:  5027783488,
		Note:        "Fast tool-calling general/coding model (fits 32K q4_0 KV in 12 GB)",
	},
	{
		ID:          "qwen3-14b-q4km",
		DisplayName: "Qwen3-14B (Q4_K_M, 8.38 GiB)",
		Filename:    "Qwen3-14B-Q4_K_M.gguf",
		URL:         "https://huggingface.co/Qwen/Qwen3-14B-GGUF/resolve/main/Qwen3-14B-Q4_K_M.gguf",
		ExpectedSz:  9001752960,
		Note:        "Strongest 100% VRAM tool caller & reasoner (32K q4_0 KV)",
	},
}

// DownloadModel fetches a single CuratedModel into <modelsDir>/<Filename> with .part resume support.
func DownloadModel(modelsDir string, m CuratedModel) (string, error) {
	if err := os.MkdirAll(modelsDir, 0o755); err != nil {
		return "", err
	}
	finalPath := filepath.Join(modelsDir, m.Filename)
	if info, err := os.Stat(finalPath); err == nil {
		if m.ExpectedSz > 0 && info.Size() == m.ExpectedSz {
			fmt.Printf("  [SKIP] %s already complete (%d bytes)\n", m.Filename, info.Size())
			return finalPath, nil
		}
	}

	partPath := finalPath + ".part"
	fmt.Printf("  [GET]  %s (%.2f GiB)...\n", m.Filename, float64(m.ExpectedSz)/(1024*1024*1024))
	if err := downloadWithProgress(m.URL, partPath, m.ExpectedSz, true); err != nil {
		return "", err
	}
	if err := os.Rename(partPath, finalPath); err != nil {
		return "", err
	}
	return finalPath, nil
}

func downloadWithProgress(url, dstPath string, expectedSize int64, allowResume bool) error {
	var startOffset int64
	if allowResume {
		if info, err := os.Stat(dstPath); err == nil && info.Size() > 0 {
			startOffset = info.Size()
		}
	}

	client := &http.Client{Timeout: 0}
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", "rx6700xt-afterburner-installer")
	if startOffset > 0 {
		req.Header.Set("Range", fmt.Sprintf("bytes=%d-", startOffset))
	}

	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	flags := os.O_CREATE | os.O_WRONLY
	if resp.StatusCode == http.StatusPartialContent && startOffset > 0 {
		flags |= os.O_APPEND
	} else if resp.StatusCode == http.StatusOK {
		startOffset = 0
		flags |= os.O_TRUNC
	} else if resp.StatusCode == http.StatusRequestedRangeNotSatisfiable && expectedSize > 0 && startOffset == expectedSize {
		return nil
	} else {
		return fmt.Errorf("HTTP %d fetching %s", resp.StatusCode, url)
	}

	totalSize := expectedSize
	if resp.ContentLength > 0 {
		totalSize = startOffset + resp.ContentLength
	}

	out, err := os.OpenFile(dstPath, flags, 0o644)
	if err != nil {
		return err
	}
	defer out.Close()

	buf := make([]byte, 256*1024)
	downloaded := startOffset
	started := time.Now()
	lastPrint := time.Time{}

	for {
		n, readErr := resp.Body.Read(buf)
		if n > 0 {
			if _, wErr := out.Write(buf[:n]); wErr != nil {
				return wErr
			}
			downloaded += int64(n)
			if time.Since(lastPrint) >= 400*time.Millisecond || readErr == io.EOF {
				elapsed := time.Since(started).Seconds()
				speedMBs := 0.0
				if elapsed > 0.1 {
					speedMBs = float64(downloaded-startOffset) / (1024 * 1024) / elapsed
				}
				if totalSize > 0 {
					pct := float64(downloaded) * 100.0 / float64(totalSize)
					fmt.Printf("\r    %.1f%% (%.1f / %.1f MB @ %.1f MB/s)   ",
						pct, float64(downloaded)/(1024*1024), float64(totalSize)/(1024*1024), speedMBs)
				} else {
					fmt.Printf("\r    %.1f MB (@ %.1f MB/s)   ", float64(downloaded)/(1024*1024), speedMBs)
				}
				lastPrint = time.Now()
			}
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			fmt.Println()
			return readErr
		}
	}
	fmt.Println()
	return nil
}

// DiscoverGGUFs returns sorted model IDs (without .gguf extension) found inside modelsDir.
func DiscoverGGUFs(modelsDir string) []string {
	entries, err := os.ReadDir(modelsDir)
	if err != nil {
		return nil
	}
	var ids []string
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		if strings.HasSuffix(strings.ToLower(name), ".gguf") {
			ids = append(ids, strings.TrimSuffix(name, filepath.Ext(name)))
		}
	}
	return ids
}
