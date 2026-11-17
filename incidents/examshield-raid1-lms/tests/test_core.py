from examshield.core import MirrorLab
def test_failure_and_rebuild(tmp_path):
    l=MirrorLab(tmp_path);x=l.submit('s1','final','answer','req1')
    assert l.read('s1','final','req1')['digest']==x['digest']
    assert l.fail(1);l.poll();assert l.status()['detection_latency_s']>=0
    for i in range(30):l.submit('s2','final',str(i),str(i))
    y=l.submit('s1','final','answer','req1')
    assert y['duplicate'] and y['receipt']==x['receipt']
    l.recover(1,0);l.rebuild_thread.join(timeout=20)
    assert l.status()['raid_state']=='healthy'
    assert l.verify()['matches']
    assert l.verify()['disk_a_objects']==31
def test_total_outage(tmp_path):
    l=MirrorLab(tmp_path);l.fail(0);l.fail(1)
    try:l.submit('s','e','answer','r')
    except OSError:pass
    else:raise AssertionError('write unexpectedly succeeded')
    assert l.status()['write_errors']==1
