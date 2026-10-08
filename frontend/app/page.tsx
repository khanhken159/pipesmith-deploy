import { ActivityFeed, Hero, NewRequestCard, RecentRunsCard, SystemOverview } from "@/components/home/Dashboard";

export default function HomePage() {
  return (
    <div className="dashboard">
      <Hero />
      <SystemOverview />
      <RecentRunsCard />
      <div className="dash-side">
        <NewRequestCard />
        <ActivityFeed />
      </div>
    </div>
  );
}
