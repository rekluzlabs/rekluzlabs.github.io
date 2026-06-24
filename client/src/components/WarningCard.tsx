import { Card } from "@/components/ui/card";

interface WarningCardProps {
  icon: string;
  label: string;
  color: string;
  meaning: string;
  fix: string;
}

export default function WarningCard({
  icon,
  label,
  color,
  meaning,
  fix,
}: WarningCardProps) {
  return (
    <Card className="overflow-hidden border-0 shadow-sm hover:shadow-md transition-shadow duration-200 bg-card">
      <div className="p-3 sm:p-4">
        {/* Icon Container - Compact but visible */}
        <div
          className="w-20 h-20 sm:w-24 sm:h-24 rounded-lg border-3 flex items-center justify-center bg-white mx-auto mb-3"
          style={{ borderColor: color }}
        >
          <img
            src={icon}
            alt={label}
            className="w-14 h-14 sm:w-16 sm:h-16 object-contain"
          />
        </div>

        {/* Label */}
        <h3
          className="text-sm sm:text-base font-bold text-center mb-2 leading-tight"
          style={{ color }}
        >
          {label}
        </h3>

        {/* Meaning */}
        <p className="text-xs sm:text-sm text-muted-foreground italic mb-2 leading-snug text-center">
          {meaning}
        </p>

        {/* Fix Instructions */}
        <div className="bg-secondary/30 rounded-md p-2 sm:p-3 border border-secondary/50">
          <p className="text-xs sm:text-sm text-foreground leading-relaxed font-medium">
            {fix}
          </p>
        </div>
      </div>
    </Card>
  );
}
