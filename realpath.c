#include<limits.h>
#include<stdlib.h>
#include<stdio.h>

int main(int argc, char **argv)
{
    if (argc > 1)
        printf("%s\n", realpath(argv[1], NULL));
    else
        printf("\n");
    return 0;
}


