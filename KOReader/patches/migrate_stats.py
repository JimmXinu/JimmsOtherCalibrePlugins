import apsw
import re

from collections import defaultdict

## note the t -- work on a copy first.
db = apsw.Connection('tstatistics.sqlite3')

"""
One-time use script for fixing my statistics from pre-normalized title
and 2-statistics-with-uuid-key.lua

Does *not* create or populate uuid table.

 ** This is not needed if stats data cleared instead. **

Copy the DB over to a python capable machine to migrate becuase I'm
not figuring this out in lua.

id integer PRIMARY KEY autoincrement,
title text,
authors text,
notes      integer,
last_open  integer,
highlights integer,
pages      integer,
series text,
language text,
md5 text,
total_read_time  integer,
total_read_pages integer
"""

def read_book_table():
    
    book_rows = {}
    book_ids_by_name = defaultdict(list)
    ident_rows = {}
    needs_rows = set()

    allsql = "select id,title,authors,md5,pages,last_open,series,language,notes,highlights,total_read_time,total_read_pages from book order by last_open"
    for row in db.execute(allsql):
        id_book = row[0]
        book_rows[id_book] = row
        
        title = row[1]
        authors = row[2]
        norm_title = re.sub(r"^(000 )?(.+)$",r"\2",title)
        #print("title:%s -> %s"%(title[:100],norm_title[:100]))
        norm_title = re.sub(r"^(.+?)( \([0-9,]+\).*)?$",r"\1",norm_title)
        #print("title:%s -> %s"%(title[:100],norm_title[:100]))
    
        ## Order query by last_open, so last entry has best md5 & last_open.
        book_ids_by_name[norm_title].append(id_book)
        if title == norm_title:
            ident_rows[norm_title] = id_book
    
    for nt in book_ids_by_name.keys():
        if nt not in ident_rows:
            needs_rows.add(nt)
            
    print(len(book_ids_by_name))
    print(book_ids_by_name)
    print()
    print(ident_rows)
    print("\n\nneeds_rows:%s\n\n"%needs_rows)

    return book_rows, book_ids_by_name, ident_rows, needs_rows


book_rows, book_ids_by_name, ident_rows, needs_rows = read_book_table()

## Adding rows for needs_rows
for norm_title in needs_rows:
    print(book_ids_by_name[norm_title])
    book_id = book_ids_by_name[norm_title][-1]
    b=book_rows[book_id]
    vals = [norm_title]
    vals.extend(b[2:8])
    vals[4]=vals[4]+1 # bump last_open by 1 just to make sure it's last
    print(vals)
#    for row in book_ids_by_name[t]:
    insertsql = """
    insert into book (title,authors,md5,pages,last_open,series,language) values (?,?,?,?,?,?,?)
    """
    db.execute(insertsql,vals)

## Re-read book table so new created ident rows are included in lists
book_rows, book_ids_by_name, ident_rows, needs_rows = read_book_table()

for norm_title in book_ids_by_name.keys():
    print(norm_title)
    id_list = book_ids_by_name[norm_title]
    print(id_list)

    ## sum up the count columns -- This part will inflate values if run
    ## more than once without also removing the non-norm rows below.
    sumsql = "select sum(notes),sum(highlights),sum(total_read_time),sum(total_read_pages) from book where id in (%s)"
    s = sumsql % ','.join(['?']*len(id_list))
    print(s)
    sum_notes, sum_highlights, sum_total_read_time, sum_total_read_pages = 0, 0, 0, 0
    for r in db.execute(s,id_list):
        sum_notes, sum_highlights, sum_total_read_time, sum_total_read_pages = r

    print(sum_notes, sum_highlights, sum_total_read_time, sum_total_read_pages)
    updatesql = """
    update book set
    notes=?, highlights=?, total_read_time=?, total_read_pages=?
    where id=?
    """
    # last id in list is most recent.
    db.execute(updatesql,(sum_notes,
                          sum_highlights,
                          sum_total_read_time,
                          sum_total_read_pages,
                          id_list[-1]))


    ## Move page_stat_data entries to the ident row.
    updatedatasql = "update page_stat_data set id_book=? where id_book in (%s)"
    s = updatedatasql % ','.join(['?']*len(id_list))
    print(s)
    vals=[id_list[-1]]
    vals.extend(id_list)
    print(vals)
    db.execute(s,vals)

    ## delete the book entries that just had all their page_stat_data
    ## transfered to the norm titled records
    del_list = id_list[:-1]
    deletesql = "delete from book where id in (%s)"
    s = deletesql % ','.join(['?']*len(del_list))
    print(s)
    print(del_list)
    db.execute(s,del_list)
    
db.close()
