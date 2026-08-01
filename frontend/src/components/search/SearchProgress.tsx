import { Progress } from "@/components/ui/progress";
import { SearchTimeline } from "@/components/search/SearchTimeline";

interface SearchProgressProps {
  uploadProgress: number;
}

export function SearchProgress({ uploadProgress }: SearchProgressProps) {
  const uploadDone = uploadProgress >= 100;

  return (
    <div className="mx-auto flex w-full max-w-md flex-col items-center gap-8 py-16">
      <div className="w-full space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium text-foreground">
            {uploadDone ? "Analyzing" : "Uploading"}
          </span>
          <span className="text-muted-foreground">{uploadDone ? "" : `${uploadProgress}%`}</span>
        </div>
        <Progress value={uploadDone ? 100 : uploadProgress} />
      </div>

      <div className="w-full">
        <SearchTimeline mode="live" uploadDone={uploadDone} />
      </div>
    </div>
  );
}
