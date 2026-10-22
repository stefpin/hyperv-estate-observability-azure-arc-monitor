# Notices

## Not an official product

This repository is an independent reference implementation and teaching resource. It is not an official Microsoft
product, it is not supported or endorsed by Microsoft or by any other company named in it, and it comes with no warranty
(see [LICENSE](LICENSE)). Use it at your own risk and review every script before you run it against a subscription you
care about.

## Trademarks

Microsoft, Azure, Azure Arc, Azure Monitor, Azure Functions, Azure Managed Grafana, Hyper-V, SQL Server, Windows Server
and PowerShell are trademarks of the Microsoft group of companies. Grafana is a trademark of Grafana Labs. Red Hat and
Red Hat Enterprise Linux are trademarks of Red Hat, Inc. All other product names are trademarks of their respective
owners. They are used here only to identify the products the lab observes and runs on.

## Third-party software used by the shift-report application

The application declares these Python dependencies in `shift-report/app/requirements.txt`. They are not included in this
repository; you install them yourself and their licences apply to you.

| Package | Licence (from the package metadata) |
|---|---|
| azure-functions | MIT |
| azure-identity | MIT |
| azure-storage-blob | MIT |
| azure-storage-queue | MIT |
| azure-communication-email | MIT |
| requests | Apache-2.0 |
| XlsxWriter | BSD-2-Clause |
| ReportLab | BSD |
| PyMuPDF | Dual licence: GNU AGPL-3.0 or Artifex commercial licence |

**PyMuPDF.** The application imports PyMuPDF (`fitz`) to merge and inspect PDF pages. PyMuPDF is offered under the GNU
Affero General Public License 3.0 or under a commercial licence from Artifex. This repository's own code is MIT-licensed
and does not copy PyMuPDF, but if you deploy or distribute an application that uses PyMuPDF you must comply with its
licence (AGPL-3.0 terms, including offering corresponding source to users who interact with it over a network, or a
commercial licence) or replace that dependency. Seek legal advice if you are unsure which applies to you.

## Media and other material you must obtain yourself

The lab guide names the operating-system and SQL Server installation media and gives checksums so that you can verify
the files you download. No installation media, licence keys or evaluation software are included. You are responsible
for accepting the vendors' licence terms and for using evaluation editions only as those terms allow.

## Diagram icons

The architecture diagram (`diagrams/architecture-overview.drawio` and its PNG export) uses Microsoft Azure architecture
icons from the draw.io shape library. Microsoft's terms for the use of Azure icons in architecture diagrams apply to
those icons.

## Neutral brand images

The images in `shift-report/app/config/` (`banner.png`, `email-branding/brand-primary.png`,
`email-branding/brand-secondary.png`) and the banner embedded in the dashboards are generated placeholders created for
this repository. Replace them with your own approved artwork before you use the report e-mail for real.
