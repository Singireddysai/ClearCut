import { motion } from "framer-motion";
import { Download, FileText, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { OutputsResponse } from "@/api/client";
import { downloadUrl, transcriptUrl } from "@/api/client";

interface OutputsPanelProps {
  data: OutputsResponse;
  jobId: string;
}

const lengthLabel: Record<string, string> = {
  short: "Short",
  medium: "Medium",
  long: "Long",
};

export function OutputsPanel({ data, jobId }: OutputsPanelProps) {
  if (data.outputs.length === 0 && data.transcripts.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Loader2 className="h-10 w-10 text-muted animate-spin mb-4" />
          <p className="text-muted">Outputs are still being generated…</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="space-y-4"
    >
      {data.outputs.length > 0 && (
        <Card>
          <CardHeader>
            <h3 className="text-base font-semibold">Summary videos</h3>
            <p className="text-sm text-muted">Download the summarized clip for each length.</p>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            {data.outputs.map((out) => (
              <a
                key={out.length}
                href={downloadUrl(jobId, out.length)}
                download={out.filename}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-surface-elevated px-5 py-2 text-sm font-medium text-zinc-200 transition-colors hover:bg-zinc-800/80 hover:border-zinc-600"
              >
                <Download className="h-4 w-4" />
                {lengthLabel[out.length] ?? out.length}
              </a>
            ))}
          </CardContent>
        </Card>
      )}
      {data.transcripts.length > 0 && (
        <Card>
          <CardHeader>
            <h3 className="text-base font-semibold">Transcripts</h3>
            <p className="text-sm text-muted">Text summary for each length.</p>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            {data.transcripts.map((t) => (
              <a
                key={t.length}
                href={transcriptUrl(jobId, t.length)}
                download={t.filename}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-transparent px-5 py-2 text-sm font-medium text-zinc-300 transition-colors hover:bg-accent-muted hover:border-accent/50"
              >
                <FileText className="h-4 w-4" />
                {lengthLabel[t.length] ?? t.length}
              </a>
            ))}
          </CardContent>
        </Card>
      )}
    </motion.div>
  );
}
