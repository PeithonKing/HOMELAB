package main

import (
	"encoding/xml"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
)

// --- XML Structs ---
// These structs define the exact shape of standard RSS 2.0
// The `xml:"tagname"` tells Go exactly what XML tag to generate!
type RSS struct {
	XMLName xml.Name `xml:"rss"`
	Version string   `xml:"version,attr"` // ,attr makes it an attribute <rss version="2.0">
	Channel Channel  `xml:"channel"`
}

type Channel struct {
	Title       string `xml:"title"`
	Link        string `xml:"link"`
	Description string `xml:"description"`
	Items       []Item `xml:"item"` // Array of items!
}

type Item struct {
	Title       string    `xml:"title"`
	Link        string    `xml:"link"`
	Description string    `xml:"description"`
	PubDate     string    `xml:"pubDate"`
	Guid        string    `xml:"guid"`
	Enclosure   Enclosure `xml:"enclosure"`
}

type Enclosure struct {
	Url    string `xml:"url,attr"`
	Type   string `xml:"type,attr"`
	Length string `xml:"length,attr"`
}

const outputFile = "ollama_rss.xml"
const tempFile = "ollama_rss.xml.tmp"

// --- The Fetcher ---
func fetchAndBuildRSS() {
	fmt.Println("[Worker] Fetching Ollama blog at", time.Now().Format(time.Kitchen))

	// 1. Make HTTP GET request to blog
	res, err := http.Get("https://ollama.com/blog")
	if err != nil {
		log.Println("Error fetching blog:", err)
		return
	}
	defer res.Body.Close() // ALWAYS close the connection when function exits

	// 2. Parse HTML using goquery (just like BeautifulSoup!)
	doc, err := goquery.NewDocumentFromReader(res.Body)
	if err != nil {
		log.Println("Error parsing HTML:", err)
		return
	}

	// 3. Build the base of our XML feed
	feed := RSS{
		Version: "2.0",
		Channel: Channel{
			Title:       "Ollama Blog",
			Link:        "https://ollama.com/blog",
			Description: "Latest posts from Ollama blog",
		},
	}

	// 4. Find all blog posts using CSS selectors
	doc.Find("section.mx-auto a.group").Each(func(i int, s *goquery.Selection) {
		title := strings.TrimSpace(s.Find("h2").Text())
		href, _ := s.Attr("href")
		link := "https://ollama.com" + href
		pubDate := strings.TrimSpace(s.Find("h3").Text())
		description := strings.TrimSpace(s.Find("p").Text())

		// Create an Item and append it to our feed
		feed.Channel.Items = append(feed.Channel.Items, Item{
			Title:       title,
			Link:        link,
			Description: description,
			PubDate:     pubDate,
			Guid:        link,
			Enclosure: Enclosure{
				Url:    "https://images.seeklogo.com/logo-png/59/1/ollama-logo-png_seeklogo-593420.png",
				Type:   "image/png",
				Length: "100",
			},
		})
	})

	// 5. Convert our Go Struct into beautiful indented XML bytes
	xmlBytes, err := xml.MarshalIndent(feed, "", "  ")
	if err != nil {
		log.Println("Error generating XML:", err)
		return
	}

	// We MUST add the XML header manually, Marshal doesn't do it
	finalXML := []byte(xml.Header + string(xmlBytes))

	// 6. ATOMIC WRITE TO DISK
	// First, write to temporary file
	err = os.WriteFile(tempFile, finalXML, 0644)
	if err != nil {
		log.Println("Error writing temp file:", err)
		return
	}

	// Second, atomically rename it! (OS level magic)
	err = os.Rename(tempFile, outputFile)
	if err != nil {
		log.Println("Error renaming file:", err)
		return
	}

	fmt.Println("[Worker] Successfully updated RSS feed atomically!")
}

// --- Background Loop ---
func backgroundWorker() {
	// Run it immediately once on startup
	fetchAndBuildRSS()

	// Then setup a Ticker that ticks every 1 hour
	ticker := time.NewTicker(1 * time.Hour)
	
	// 'range ticker.C' blocks until the ticker ticks, then loops forever
	for range ticker.C {
		fetchAndBuildRSS()
	}
}

// --- The Web Server ---
func main() {
	// 1. Start the background fetching thread
	go backgroundWorker()

	// 2. Define HTTP route
	http.HandleFunc("/rss", func(w http.ResponseWriter, r *http.Request) {
		// http.ServeFile is insanely fast. It handles reading the file from disk, 
		// setting all the correct HTTP headers, and streaming it to the user.
		// Since our disk write is atomic, this will NEVER read corrupted data!
		http.ServeFile(w, r, outputFile)
	})

	// 3. Start Web Server
	fmt.Println("[Server] Started fast file-server on http://localhost:5500/rss")
	err := http.ListenAndServe(":5500", nil)
	if err != nil {
		log.Fatal("Server crashed:", err)
	}
}
