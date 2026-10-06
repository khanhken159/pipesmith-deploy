import { PendingAction } from "@/components/run/PendingAction";
import { ResultCard } from "@/components/run/ResultCard";
import { SpecCard } from "@/components/run/SpecCard";
import { Timeline } from "@/components/run/Timeline";

export default function RunOverviewPage() {
  return (
    <>
      <PendingAction />
      <div className="grid-2">
        <div className="stack">
          <Timeline />
          <ResultCard />
        </div>
        <SpecCard />
      </div>
    </>
  );
}
