import { useState } from 'react';
import { JobRunsPanel } from './JobRunsPanel';
import { TaskRunsPanel } from './TaskRunsPanel';
import { SkillRunsPanel } from './SkillRunsPanel';
import { CapabilityPanel } from './CapabilityPanel';

type Props = {
  accessToken: string;
};

type Tab = 'jobs' | 'tasks' | 'skills' | 'capabilities';

export function OperationsPanel({ accessToken }: Props) {
  const [tab, setTab] = useState<Tab>('jobs');

  return (
    <section>
      <h2>Operations</h2>

      <nav>
        <button onClick={() => setTab('jobs')}>Jobs</button>
        <button onClick={() => setTab('tasks')}>Tasks</button>
        <button onClick={() => setTab('skills')}>Skills</button>
        <button onClick={() => setTab('capabilities')}>Capabilities</button>
      </nav>

      {tab === 'jobs' ? <JobRunsPanel accessToken={accessToken} /> : null}
      {tab === 'tasks' ? <TaskRunsPanel accessToken={accessToken} /> : null}
      {tab === 'skills' ? <SkillRunsPanel accessToken={accessToken} /> : null}
      {tab === 'capabilities' ? <CapabilityPanel accessToken={accessToken} /> : null}
    </section>
  );
}
