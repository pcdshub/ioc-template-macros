#include<limits.h>
#include<stdlib.h>
#include<stdio.h>

int main(int argc, char **argv)
{
    char *s = NULL;
    if (argc > 1)
        s = realpath(argv[1], NULL);
    if (s)
        printf("%s\n", s);
    else
        printf("\n");
    return 0;
}


