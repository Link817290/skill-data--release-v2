#include <cjson/cJSON_Utils.h>

int main(void)
{
    cJSON *document = cJSON_CreateObject();
    cJSON_Delete(document);
    return 0;
}
