"""Read completed FFmpeg progress records while its writer is still active."""
def samples(text):
    result=[];record={}
    for line in text.splitlines(keepends=True):
        if not line.endswith(('\n','\r')):break
        key,sep,value=line.strip().partition('=')
        if not sep:continue
        record[key]=value
        if key=='progress' and value in ('continue','end'):
            result.append(record);record={}
    return result


def numbers(records,key):
    return [int(row[key]) for row in records if row.get(key,'').lstrip('-').isdigit()]


def advancing(values):
    # One duplicate status report is not proof of a stalled encoder. A real
    # stall still fails this short window, file-age checks and timeline guard.
    return len(values)>=2 and values[-1]>min(values[-4:])
