import { useSyncExternalStore } from 'react';

import { getUploadJob, getWardrobeBatch, uploadWardrobeBatch, uploadWardrobePhoto } from '@/lib/wardrobeApi';
import type { SelectedItemPhoto } from '@/lib/pickItemPhoto';

/**
 * 옷 등록 진행 상황 — 화면이 아니라 여기서 돌린다.
 *
 * 등록은 서버가 큐에 넣고 처리하므로, 사용자가 등록 화면을 닫아도 처리는 계속된다.
 * 폴링을 화면에 두면 화면을 닫는 순간 결과를 놓치므로 스토어로 올렸다.
 * 옷장 화면이 이걸 구독해 '등록 중'을 보여주고, 끝나면 목록을 새로 고친다.
 */

export type UploadPhase = 'uploading' | 'processing' | 'failed';

export type UploadJobState = {
  /** 화면에서 구분하기 위한 로컬 키 (서버 job_id 는 접수 후에 생긴다) */
  key: string;
  phase: UploadPhase;
  error?: string;
  progress?: string;
};

/** 폴링 간격·한도 — 누끼+캡셔닝이 GPU 큐를 타므로 즉시 끝나지 않는다. */
const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 120_000;

let jobs: UploadJobState[] = [];
/** 하나 끝날 때마다 증가. 옷장이 이 값을 보고 목록을 다시 불러온다. */
let completed = 0;
let seq = 0;

const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((l) => l());
}

function update(key: string, patch: Partial<UploadJobState>) {
  jobs = jobs.map((j) => (j.key === key ? { ...j, ...patch } : j));
  notify();
}

function drop(key: string) {
  jobs = jobs.filter((j) => j.key !== key);
  notify();
}

export const uploadJobs = {
  getJobs: () => jobs,
  getCompleted: () => completed,

  /** 사진 한 장을 올리고 처리가 끝날 때까지 따라간다. 화면이 닫혀도 계속된다. */
  start(uri: string, opts?: { name?: string; mimeType?: string }) {
    const key = `u${++seq}`;
    jobs = [...jobs, { key, phase: 'uploading' }];
    notify();

    (async () => {
      let jobId: string;
      try {
        jobId = (await uploadWardrobePhoto(uri, opts)).job_id;
      } catch (e) {
        update(key, {
          phase: 'failed',
          error: e instanceof Error ? e.message : '사진을 올리지 못했어요',
        });
        return;
      }
      update(key, { phase: 'processing' });

      const startedAt = Date.now();
      /* 재귀 setTimeout — setInterval 은 응답이 간격보다 느릴 때 요청이 겹친다. */
      const poll = async () => {
        try {
          const job = await getUploadJob(jobId);
          if (job.status === 'DONE') {
            drop(key);
            completed += 1;
            notify();
            return;
          }
          if (job.status === 'FAILED') {
            update(key, {
              phase: 'failed',
              error: job.error_message || '사진을 처리하지 못했어요',
            });
            return;
          }
          if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
            update(key, {
              phase: 'failed',
              error: '처리가 오래 걸리고 있어요. 잠시 후 옷장을 새로고침해 주세요.',
            });
            return;
          }
          setTimeout(poll, POLL_INTERVAL_MS);
        } catch (e) {
          update(key, {
            phase: 'failed',
            error: e instanceof Error ? e.message : '처리 상태를 확인하지 못했어요',
          });
        }
      };
      setTimeout(poll, POLL_INTERVAL_MS);
    })();
  },

  startBatch(photos: SelectedItemPhoto[]) {
    const key = `b${++seq}`;
    jobs = [...jobs, { key, phase: 'uploading', progress: `0/${photos.length}장` }];
    notify();

    (async () => {
      let batchId: string;
      let interval = 3000;
      try {
        const batch = await uploadWardrobeBatch(photos);
        batchId = batch.batch_id;
        interval = batch.poll_after_ms;
        update(key, { phase: 'processing' });
      } catch (e) {
        update(key, { phase: 'failed', error: e instanceof Error ? e.message : '일괄 등록에 실패했어요' });
        return;
      }

      const poll = async () => {
        try {
          const batch = await getWardrobeBatch(batchId);
          update(key, { progress: `${batch.counts.done + batch.counts.failed}/${batch.counts.total}장` });
          if (batch.status === 'DONE') {
            drop(key); completed += 1; notify(); return;
          }
          if (batch.status === 'PARTIAL') {
            completed += 1;
            update(key, { phase: 'failed', error: `${batch.counts.done}장은 등록했고 ${batch.counts.failed}장은 실패했어요.` });
            return;
          }
          if (batch.status === 'FAILED') {
            update(key, { phase: 'failed', error: '선택한 사진을 처리하지 못했어요.' });
            return;
          }
          setTimeout(poll, batch.poll_after_ms ?? interval);
        } catch (e) {
          update(key, { phase: 'failed', error: e instanceof Error ? e.message : '처리 상태를 확인하지 못했어요' });
        }
      };
      setTimeout(poll, interval);
    })();
  },

  /** 실패 알림을 사용자가 닫는다 */
  dismiss(key: string) {
    drop(key);
  },

  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useUploadJobs(): UploadJobState[] {
  return useSyncExternalStore(uploadJobs.subscribe, uploadJobs.getJobs, uploadJobs.getJobs);
}

/** 등록이 하나 끝날 때마다 값이 바뀐다 — 목록을 다시 불러올 신호. */
export function useUploadCompleted(): number {
  return useSyncExternalStore(uploadJobs.subscribe, uploadJobs.getCompleted, uploadJobs.getCompleted);
}
