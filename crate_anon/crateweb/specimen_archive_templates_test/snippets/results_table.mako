## results_table.mako
<%page args="cursor"/>

<%!
from cardinal_pythonlib.dbfunc import genrows, get_fieldnames_from_cursor
%>

<table>
    <tr>
        %for col in get_fieldnames_from_cursor(cursor):
            <th>${col}</th>
        %endfor
    </tr>
    %for row in genrows(cursor):
        <tr>
            %for cell in row:
                <td>${cell}</td>
            %endfor
        </tr>
    %endfor
</table>
