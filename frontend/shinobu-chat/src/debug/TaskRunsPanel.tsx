import { useEffect, useState } from 'react';
import { listTaskRuns } from '../api/operations';

type Props = {
  accessToken: string;
};

export function TaskRunsPanel({ accessToken }: Props) {
  const [data, setData] = useState<{ tasks: Array<Record<string, unknown>> } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listTaskRuns(accessToken)
      .then((d) => setData(d as { tasks: Array<Record<string, unknown>> }))
      .finally(() => setLoading(false));
  }, [accessToken]);

  if (loading) return <p>Loading tasks...</p>;
  const tasks = data?.tasks ?? [];
  if (tasks.length === 0) return <p>No task runs recorded.</p>;

  return (
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Type</th>
          <th>Status</th>
          <th>Title</th>
          <th>Progress</th>
        </tr>
      </thead>
      <tbody>
        {tasks.map((t) => (
          <tr key={t.id as string}>
            <td>{(t.id as string).slice(0, 12)}...</td>
            <td>{t.task_type as string}</td>
            <td>{t.status as string}</td>
            <td>{t.title as string}</td>
            <td>{t.progress as number}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
