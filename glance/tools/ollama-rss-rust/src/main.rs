use axum::{routing::get, Router};
use quick_xml::se::to_string;
use reqwest::Client;
use scraper::{Html, Selector};
use serde::Serialize;
use std::fs;
use std::time::Duration;
use tokio::time;

// --- XML Structs using Serde ---
// In Rust, macros (the '#' things) write the parsing/generating code for us!
#[derive(Serialize)]
#[serde(rename = "rss")] // Tell it to output <rss> tag instead of <Rss>
struct Rss {
    #[serde(rename = "@version")] // The '@' tells quick-xml this is an Attribute!
    version: String,
    channel: Channel,
}

#[derive(Serialize)]
struct Channel {
    title: String,
    link: String,
    description: String,
    #[serde(rename = "item")]
    items: Vec<Item>, // Vec is Rust's version of a Slice (Dynamic Array)
}

#[derive(Serialize)]
struct Item {
    title: String,
    link: String,
    description: String,
    #[serde(rename = "pubDate")]
    pub_date: String, // Rust likes snake_case, so we rename it to camelCase for XML
    guid: String,
    enclosure: Enclosure,
}

#[derive(Serialize)]
struct Enclosure {
    #[serde(rename = "@url")]
    url: String,
    #[serde(rename = "@type")]
    ty: String, // 'type' is a reserved keyword in Rust, so we use 'ty' and rename it
    #[serde(rename = "@length")]
    length: String,
}

const OUTPUT_FILE: &str = "ollama_rss.xml";
const TEMP_FILE: &str = "ollama_rss.xml.tmp";

// --- The Fetcher ---
// 'async fn' means this function can yield execution while waiting for network
async fn fetch_and_build_rss(client: &Client) {
    println!("[Worker] Fetching Ollama blog...");

    // 1. Fetch HTML
    // 'match' is how Rust forces u to handle Errors. No silent crashing!
    let html = match client.get("https://ollama.com/blog").send().await {
        Ok(resp) => resp.text().await.unwrap_or_default(),
        Err(e) => {
            eprintln!("Error fetching blog: {}", e);
            return;
        }
    };

    // 2. Parse HTML
    let document = Html::parse_document(&html);
    
    // unwrap() means "If this fails, crash the program". 
    // We use it here because we know our own CSS selectors are valid strings.
    let post_selector = Selector::parse("section.mx-auto a.group").unwrap();
    let h2_selector = Selector::parse("h2").unwrap();
    let h3_selector = Selector::parse("h3").unwrap();
    let p_selector = Selector::parse("p").unwrap();

    // 3. Build the base of our XML feed
    let mut feed = Rss {
        version: "2.0".to_string(), // Rust strict string types require explicit conversions
        channel: Channel {
            title: "Ollama Blog".to_string(),
            link: "https://ollama.com/blog".to_string(),
            description: "Latest posts from Ollama blog".to_string(),
            items: Vec::new(),
        },
    };

    // 4. Extract items
    for element in document.select(&post_selector) {
        // Option/Result unwrapping is very strict in Rust!
        let title = element.select(&h2_selector).next().map(|n| n.inner_html()).unwrap_or_default().trim().to_string();
        let href = element.value().attr("href").unwrap_or_default();
        let link = format!("https://ollama.com{}", href);
        let pub_date = element.select(&h3_selector).next().map(|n| n.inner_html()).unwrap_or_default().trim().to_string();
        let description = element.select(&p_selector).next().map(|n| n.inner_html()).unwrap_or_default().trim().to_string();

        feed.channel.items.push(Item {
            title,
            link: link.clone(), // We have to .clone() here to satisfy the Borrow Checker
            description,
            pub_date,
            guid: link,
            enclosure: Enclosure {
                url: "https://images.seeklogo.com/logo-png/59/1/ollama-logo-png_seeklogo-593420.png".to_string(),
                ty: "image/png".to_string(),
                length: "100".to_string(),
            },
        });
    }

    // 5. Generate XML string
    let xml_body = match to_string(&feed) {
        Ok(x) => x,
        Err(e) => {
            eprintln!("Error serializing XML: {}", e);
            return;
        }
    };
    
    let final_xml = format!(r#"<?xml version="1.0" encoding="UTF-8"?>{}"#, xml_body);

    // 6. ATOMIC WRITE
    // 'if let Err' is a shorter version of 'match' when we only care about Errors
    if let Err(e) = fs::write(TEMP_FILE, final_xml) {
        eprintln!("Error writing temp file: {}", e);
        return;
    }
    if let Err(e) = fs::rename(TEMP_FILE, OUTPUT_FILE) {
        eprintln!("Error renaming file: {}", e);
        return;
    }

    println!("[Worker] Successfully updated RSS feed atomically!");
}

// --- Background Loop ---
async fn background_worker() {
    let client = Client::new();
    
    // Initial run
    fetch_and_build_rss(&client).await;

    // Setup an async timer (ticker)
    let mut interval = time::interval(Duration::from_secs(3600)); // 3600 seconds = 1 hr
    loop {
        interval.tick().await; // Yield execution until timer pops
        fetch_and_build_rss(&client).await;
    }
}

// --- The Web Server ---
// #[tokio::main] injects the massive async Tokio runtime so our main function can be async!
#[tokio::main]
async fn main() {
    // 1. Start background worker (tokio::spawn is Rust's version of Go's 'go' keyword)
    tokio::spawn(async {
        background_worker().await;
    });

    // 2. Define HTTP route using Axum (FastAPI equivalent for Rust)
    let app = Router::new().route("/rss", get(serve_rss));

    // 3. Start Web Server
    let listener = tokio::net::TcpListener::bind("0.0.0.0:5500").await.unwrap();
    println!("[Server] Started Rust server on http://localhost:5500/rss");
    
    axum::serve(listener, app).await.unwrap();
}

// Handler for HTTP Route
// Returns either a String (HTTP 200 OK) or a StatusCode (HTTP 404/500 Error)
async fn serve_rss() -> Result<String, axum::http::StatusCode> {
    match fs::read_to_string(OUTPUT_FILE) {
        Ok(content) => Ok(content),
        Err(_) => Err(axum::http::StatusCode::NOT_FOUND), // If file missing, return 404
    }
}
