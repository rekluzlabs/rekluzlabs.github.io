import { Button } from "@/components/ui/button";
import WarningCard from "@/components/WarningCard";
import { Printer } from "lucide-react";

const warnings = [
  {
    icon: "/manus-storage/water_tank_3f2747f1.png",
    label: "Water Tank",
    color: "#cc2222",
    meaning: "Tank empty or not seated",
    fix: "Fill to MAX. Push tank firmly in until light goes off.",
  },
  {
    icon: "/manus-storage/grounds_bin_ac7cc3bb.png",
    label: "Grounds Bin",
    color: "#cc2222",
    meaning: "Grounds container full",
    fix: "Machine ON: remove drip tray, empty bin, wait 5 sec, reinstall.",
  },
  {
    icon: "/manus-storage/alarm_on_67517e83.png",
    label: "Alarm — solid",
    color: "#cc2222",
    meaning: "Bin/tray missing or service door open",
    fix: "Re-seat bin & tray. Remove tank, close service door.",
  },
  {
    icon: "/manus-storage/alarm_flash_6fc267e0.png",
    label: "Alarm — flashing",
    color: "#cc6600",
    meaning: "Brew group missing or blocked",
    fix: "Turn OFF. Remove tank, open door, rinse brew group under tap, reinstall until it clicks. Close door, replace tank, turn ON.",
  },
  {
    icon: "/manus-storage/alarm_start_flash_6d64740d.png",
    label: "Alarm + Start flash",
    color: "#cc6600",
    meaning: "Air trapped in machine",
    fix: "Fill tank. Cup under frother. Press flashing Start/Stop to purge hot water.",
  },
  {
    icon: "/manus-storage/aquaclean_6d8f15c8.png",
    label: "AquaClean → blue",
    color: "#cc6600",
    meaning: "AquaClean filter needs install or replace",
    fix: "Soak filter 15 min. Insert into tank. Run activation cycle. Light turns blue when done.",
  },
  {
    icon: "/manus-storage/descaling_139444bf.png",
    label: "Calc/Clean — slow flash",
    color: "#cc6600",
    meaning: "Machine needs descaling",
    fix: "Run full Calc/Clean cycle (~30 min) with Philips descaler solution.",
  },
  {
    icon: "/manus-storage/heating_0cbb8f47.png",
    label: "Drink lights cycling",
    color: "#1a66cc",
    meaning: "Machine heating / releasing air",
    fix: "Normal start-up. Wait until all drink lights stay solid before brewing.",
  },
  {
    icon: "/manus-storage/all_flash_c22675e6.png",
    label: "ALL icons flashing",
    color: "#cc2222",
    meaning: "Machine error — needs reset",
    fix: "Unplug. Remove AquaClean filter. Refill & reseat tank. Clear pre-ground chute. Reinstall brew group. Restart. Still flashing? Cool 30 min.",
  },
];

export default function Home() {
  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-border shadow-sm">
        <div className="container max-w-7xl mx-auto px-4 py-4 sm:py-5">
          <div className="flex items-center justify-between gap-4">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <img
                src="https://d2xsxph8kpxj0f.cloudfront.net/310519663788405148/f2Mdw75A3RpCYbd8YdmibR/lattego-logo-WChiCVWTFvyiBo5tPLyqs6.webp"
                alt="LatteGo Cheat Sheet"
                className="w-10 h-10 sm:w-12 sm:h-12"
              />
              <div>
                <h1 className="text-lg sm:text-xl font-bold text-foreground">
                  LatteGo Cheat Sheet
                </h1>
                <p className="text-xs sm:text-sm text-muted-foreground">
                  Philips 3200 Warning Lights Guide
                </p>
              </div>
            </div>

            {/* Print Button */}
            <Button
              onClick={handlePrint}
              variant="outline"
              size="sm"
              className="gap-2 print:hidden"
            >
              <Printer className="w-4 h-4" />
              <span className="hidden sm:inline">Print Card</span>
              <span className="sm:hidden">Print</span>
            </Button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section
        className="relative py-8 sm:py-12 bg-cover bg-center"
        style={{
          backgroundImage:
            "url('https://d2xsxph8kpxj0f.cloudfront.net/310519663788405148/f2Mdw75A3RpCYbd8YdmibR/lattego-hero-bg-Ne6fPkoCGg9o2SjCPYbd72.webp')",
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-b from-white/80 to-white/60" />
        <div className="container max-w-7xl mx-auto px-4 relative z-10">
          <div className="text-center max-w-2xl mx-auto">
            <h2 className="text-3xl sm:text-4xl font-bold text-foreground mb-3">
              Warning Lights Quick Reference
            </h2>
            <p className="text-base sm:text-lg text-muted-foreground mb-4">
              Understand what each light means and how to fix it. Keep this guide
              handy for quick troubleshooting.
            </p>
            <div className="flex flex-wrap justify-center gap-3 text-xs sm:text-sm">
              <span className="inline-flex items-center gap-2 px-3 py-1.5 bg-red-100 text-red-700 rounded-full">
                <span className="w-2 h-2 bg-red-600 rounded-full" />
                Action Needed
              </span>
              <span className="inline-flex items-center gap-2 px-3 py-1.5 bg-amber-100 text-amber-700 rounded-full">
                <span className="w-2 h-2 bg-amber-600 rounded-full" />
                Maintenance
              </span>
              <span className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-100 text-blue-700 rounded-full">
                <span className="w-2 h-2 bg-blue-600 rounded-full" />
                Normal/Info
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Warning Cards Grid */}
      <section className="py-8 sm:py-12 bg-background">
        <div className="container max-w-7xl mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
            {warnings.map((warning, idx) => (
              <div key={idx} className="animate-in fade-in slide-in-from-bottom-4 duration-500" style={{animationDelay: `${idx * 50}ms`}}>
                <WarningCard {...warning} />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-secondary/50 border-t border-border py-6 sm:py-8">
        <div className="container max-w-7xl mx-auto px-4">
          <div className="text-center text-sm text-muted-foreground">
            <p className="mb-2">
              Icons sourced from the Philips EP3246 3200 LatteGo User Manual
            </p>
            <p>
              For complete troubleshooting, refer to your machine's official
              documentation.
            </p>
          </div>
        </div>
      </footer>

      {/* Print Styles */}
      <style>{`
        @media print {
          header, footer, .print\\:hidden {
            display: none !important;
          }
          
          body {
            background: white;
          }
          
          section:first-of-type {
            page-break-after: avoid;
          }
          
          .grid {
            grid-template-columns: 1fr 1fr !important;
            gap: 0.5rem !important;
          }
          
          .container {
            max-width: 100%;
            padding: 0.5rem;
          }
          
          @page {
            size: 5in 3in;
            margin: 0.1in;
          }
        }
      `}</style>
    </div>
  );
}
