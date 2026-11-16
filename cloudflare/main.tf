# ==============================================================================
# 1. OPENTOFU / TERRAFORM CONFIGURATION
# This block tells OpenTofu which provider plugins to download when you run `tofu init`.
# ==============================================================================
terraform {
  required_providers {
    # We are declaring that we need the Cloudflare provider to manage our infrastructure.
    cloudflare = {
      source  = "cloudflare/cloudflare"
      # We lock the version to anything in the 4.x range to ensure future updates don't break our code.
      version = "~> 4.0"
    }
  }
}

# ==============================================================================
# 2. PROVIDER SETUP
# This configures the Cloudflare plugin to authenticate using your token.
# ==============================================================================
provider "cloudflare" {
  # The API token is pulled from the variable below (which gets its value from your .env file).
  api_token = var.cloudflare_api_token
}

# ==============================================================================
# 3. VARIABLES
# These declare the inputs OpenTofu expects. Because we prefixed them with TF_VAR_ 
# in your .env file, OpenTofu automatically fills them in without pausing to ask you.
# ==============================================================================
variable "cloudflare_api_token" {
  description = "Cloudflare API Token"
  type        = string
  sensitive   = true # This prevents OpenTofu from accidentally printing your token in terminal logs.
}

variable "cloudflare_zone_id" {
  description = "Cloudflare Zone ID for peithonking.com"
  type        = string
}

variable "cloudflare_account_id" {
  description = "Cloudflare Account ID"
  type        = string
}

variable "qkbench_enabled" {
  description = "Publish the temporary qkrylov benchmark page (qkbench.peithonking.com); switched off by qkbench/expire.sh"
  type        = bool
  default     = false
}

# ==============================================================================
# 4. DNS RECORDS (GITHUB PAGES & EXTERNAL)
# Each block represents a single DNS record in your Cloudflare dashboard.
# `proxied = true` means Cloudflare hides the target IP and provides DDoS protection/SSL (Orange Cloud).
# ==============================================================================

resource "cloudflare_record" "root" {
  zone_id = var.cloudflare_zone_id
  name    = "@"                      # The root domain (peithonking.com)
  content = "peithonking.github.io"  # Where it points
  type    = "CNAME"                  # Cloudflare uses CNAME flattening for root domains
  proxied = true                     # Cloudflare Proxy enabled
}

resource "cloudflare_record" "www" {
  zone_id = var.cloudflare_zone_id
  name    = "www"
  content = "peithonking.github.io"
  type    = "CNAME"
  proxied = true
}

resource "cloudflare_record" "blogs" {
  zone_id = var.cloudflare_zone_id
  name    = "blogs"                  # The subdomain (blogs.peithonking.com)
  content = "peithonking.github.io"  # Where it points
  type    = "CNAME"                  # Record type
  proxied = true                     # Cloudflare Proxy enabled
}

resource "cloudflare_record" "cv" {
  zone_id = var.cloudflare_zone_id
  name    = "cv"
  content = "peithonking.github.io"
  type    = "CNAME"
  proxied = true
}

resource "cloudflare_record" "clipcast" {
  zone_id = var.cloudflare_zone_id
  name    = "clipcast"
  content = "peithonking.github.io"
  type    = "CNAME"
  proxied = true
}

# This record points to an external EU Proxy.
# `proxied = false` means it is DNS-Only (Grey Cloud). Traffic goes directly to the proxy, bypassing Cloudflare's shield.
resource "cloudflare_record" "mrcg" {
  zone_id = var.cloudflare_zone_id
  name    = "mrcg"
  content = "02511341f10de331caf0.cf-prod-eu-proxy.europehog.com"
  type    = "CNAME"
  proxied = false 
}

# ==============================================================================
# 5. DNS RECORDS (CLOUDFLARE TUNNEL)
# These records point traffic for your homelab apps directly into your secure Cloudflare Tunnel.
# ==============================================================================

resource "cloudflare_record" "club" {
  zone_id = var.cloudflare_zone_id
  name    = "club"
  content = "bbb60cf6-7447-4711-bd02-d64e16760e7f.cfargotunnel.com" # Your unique Tunnel URL
  type    = "CNAME"
  proxied = true
}

# Temporary static page for the qkrylov benchmark viewer. count = 0 removes the record (see qkbench/expire.sh).
resource "cloudflare_record" "qkbench" {
  count   = var.qkbench_enabled ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = "qkbench"
  content = "bbb60cf6-7447-4711-bd02-d64e16760e7f.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}

resource "cloudflare_record" "requests" {
  zone_id = var.cloudflare_zone_id
  name    = "requests"
  content = "bbb60cf6-7447-4711-bd02-d64e16760e7f.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}

resource "cloudflare_record" "notes" {
  zone_id = var.cloudflare_zone_id
  name    = "notes"
  content = "bbb60cf6-7447-4711-bd02-d64e16760e7f.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}

resource "cloudflare_record" "drive" {
  zone_id = var.cloudflare_zone_id
  name    = "drive"
  content = "bbb60cf6-7447-4711-bd02-d64e16760e7f.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}

# School documents app for the headmaster (baba_docs) — device-locked, see ~/HOMELAB/baba_docs
resource "cloudflare_record" "docs" {
  zone_id = var.cloudflare_zone_id
  name    = "docs"
  content = "bbb60cf6-7447-4711-bd02-d64e16760e7f.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}

# Signature icon host for sigil (email-open tracker), see ~/HOMELAB/sigil
resource "cloudflare_record" "cdn" {
  zone_id = var.cloudflare_zone_id
  name    = "cdn"
  content = "bbb60cf6-7447-4711-bd02-d64e16760e7f.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}

# ==============================================================================
# 6. TUNNEL INGRESS ROUTING (THE "BOUNCER")
# Even though DNS points traffic to the tunnel, the tunnel itself needs to know where 
# to send it on your local Raspberry Pi network. This configures the tunnel's brain.
# ==============================================================================

resource "cloudflare_zero_trust_tunnel_cloudflared_config" "homelab_config" {
  account_id = var.cloudflare_account_id
  tunnel_id  = "bbb60cf6-7447-4711-bd02-d64e16760e7f"
  
  config {
    # If someone asks for Jellyfin (club), send them to the Jellyfin docker container on port 8096
    ingress_rule {
      hostname = "club.peithonking.com"
      service  = "http://jellyfin:8096"
    }
    # If someone asks for Seerr (requests), send them to the Seerr docker container on port 5055
    ingress_rule {
      hostname = "requests.peithonking.com"
      service  = "http://seerr:5055"
    }
    # If someone asks for Silverbullet (notes), send them to the local server IP on port 3000
    ingress_rule {
      hostname = "notes.peithonking.com"
      service  = "http://silverbullet:3000"
    }
    # Nextcloud Office: Collabora lives under the same hostname on its own paths
    # (editor assets, discovery/capabilities, and the /cool websocket).
    ingress_rule {
      hostname = "drive.peithonking.com"
      path     = "^/(browser|hosting|cool)/"
      service  = "http://collabora:9980"
    }
    # Nextcloud (drive) - everything else on the hostname
    ingress_rule {
      hostname = "drive.peithonking.com"
      service  = "http://nextcloud:80"
    }
    # School documents app (baba_docs): FastAPI container on the shared docker network
    ingress_rule {
      hostname = "docs.peithonking.com"
      service  = "http://baba-docs:8765"
    }
    # sigil public side: only the signature icons; sigil itself 404s everything else (nginx-style).
    # Dashboard (8081) is not routed here, it stays on LAN / Tailscale.
    ingress_rule {
      hostname = "cdn.peithonking.com"
      service  = "http://sigil:8080"
    }
    dynamic "ingress_rule" {
      for_each = var.qkbench_enabled ? [1] : []
      content {
        hostname = "qkbench.peithonking.com"
        service  = "http://qkbench:80"
      }
    }
    # If someone asks for literally anything else that hits this tunnel, throw a 404 Error (Catch-all)
    ingress_rule {
      service  = "http_status:404"
    }
  }
}

# ==============================================================================
# 7. PAGE RULES (CACHING & PERFORMANCE)
# Cloudflare tries to cache web pages to make them load faster. For dynamic apps 
# (like streaming video or live text editors), caching causes lag and broken features.
# These rules explicitly tell Cloudflare NOT to cache traffic for these two subdomains.
# ==============================================================================

resource "cloudflare_page_rule" "bypass_cache_notes" {
  zone_id  = var.cloudflare_zone_id
  target   = "notes.peithonking.com/*" # Matches any URL ending after notes.peithonking.com/
  status   = "active"                  # Turns the rule ON
  priority = 1                         # Executes this rule before others

  actions {
    cache_level = "bypass"             # Do not cache anything, send all requests directly to the Pi
  }
}

resource "cloudflare_page_rule" "bypass_cache_jellyfin" {
  zone_id  = var.cloudflare_zone_id
  target   = "club.peithonking.com/*"
  status   = "active"
  priority = 2

  actions {
    cache_level = "bypass"
  }
}

resource "cloudflare_page_rule" "bypass_cache_drive" {
  zone_id  = var.cloudflare_zone_id
  target   = "drive.peithonking.com/*"
  status   = "active"
  priority = 3

  actions {
    cache_level = "bypass"
  }
}

# -------------------------------------------------------------
# WAF / FIREWALL RULES (Security)
# -------------------------------------------------------------

resource "cloudflare_ruleset" "homelab_waf" {
  zone_id     = var.cloudflare_zone_id
  name        = "default"
  description = "Custom WAF rules for homelab"
  kind        = "zone"
  phase       = "http_request_firewall_custom"

  rules {
    action      = "block"
    # cdn is exempt: mail proxies / recipients anywhere must get the icons, a block page would show a broken image.
    expression  = "(not ip.geoip.country in {\"AT\" \"IN\" \"US\"} and http.host ne \"qkbench.peithonking.com\" and http.host ne \"cdn.peithonking.com\")"
    description = "Block traffic outside AT, IN, US"
    enabled     = true
  }

  rules {
    action      = "block"
    expression  = "(http.host eq \"drive.peithonking.com\" and (starts_with(http.request.uri.path, \"/browser/dist/admin\") or starts_with(http.request.uri.path, \"/cool/adminws\") or starts_with(http.request.uri.path, \"/cool/getMetrics\")))"
    description = "Block Collabora admin console and metrics from the internet"
    enabled     = true
  }

  rules {
    action      = "managed_challenge"
    expression  = "(http.host eq \"requests.peithonking.com\") or (http.host eq \"notes.peithonking.com\")"
    description = "Turnstile Captcha for Seerr and Notes"
    enabled     = true
  }
}

# ==============================================================================
# 9. GLOBAL ZONE SETTINGS
# These are the global toggles found in your Cloudflare dashboard (like SSL, HTTPS).
# Managing them here ensures nobody can accidentally downgrade your security.
# ==============================================================================

resource "cloudflare_zone_settings_override" "peithonking_settings" {
  zone_id = var.cloudflare_zone_id
  
  settings {
    always_use_https = "on"
    ssl              = "strict" # Ensures encrypted traffic between Cloudflare and your Tunnel
    min_tls_version  = "1.2"    # Drops support for old, insecure browsers
    brotli           = "on"     # Modern web compression (faster than gzip)
  }
}
