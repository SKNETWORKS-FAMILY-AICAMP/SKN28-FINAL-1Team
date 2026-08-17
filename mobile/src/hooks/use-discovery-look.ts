import { getDiscoveryLook, type DiscoveryLookDto } from '@/lib/discoveryLookApi';
import { useEffect, useState } from 'react';

export function useDiscoveryLook(id?: string): DiscoveryLookDto | null {
  const [look, setLook] = useState<DiscoveryLookDto | null>(null);

  useEffect(() => {
    let active = true;
    setLook(null);
    if (!id || (!id.startsWith('curated-') && !id.startsWith('naver-'))) {
      return () => { active = false; };
    }
    void getDiscoveryLook(id)
      .then((result) => { if (active) setLook(result); })
      .catch(() => { if (active) setLook(null); });
    return () => { active = false; };
  }, [id]);

  return look;
}
